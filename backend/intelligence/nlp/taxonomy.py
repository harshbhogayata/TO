"""
intelligence/nlp/taxonomy.py
Skill taxonomy management: normalisation, synonym resolution, and EntityRuler integration.
"""

import logging

from django.core.cache import cache

from intelligence.constants import ALIAS_TO_CANONICAL, INITIAL_SKILLS, TAXONOMY_CACHE_TTL

logger = logging.getLogger(__name__)

_CACHE_KEY = 'intelligence:skill_taxonomy'


def get_taxonomy_lookup() -> dict[str, str]:
    """
    Return alias→canonical lookup combining DB taxonomy and constants.
    DB entries take precedence over hardcoded constants.
    Cached for 1 hour.
    """
    cached = cache.get(_CACHE_KEY)
    if cached:
        return cached

    lookup = dict(ALIAS_TO_CANONICAL)  # Start with hardcoded

    try:
        from intelligence.models import SkillTaxonomy
        for skill in SkillTaxonomy.objects.all():
            lookup[skill.canonical_name.lower()] = skill.canonical_name
            for alias in (skill.aliases or []):
                lookup[alias.lower()] = skill.canonical_name
    except Exception:
        logger.debug('SkillTaxonomy table not available, using constants only')

    cache.set(_CACHE_KEY, lookup, TAXONOMY_CACHE_TTL)
    return lookup


def normalise_skill(raw: str) -> str | None:
    """
    Normalise a raw skill string to its canonical name.
    Returns None if the skill is not in the taxonomy.
    """
    if not raw:
        return None

    lookup = get_taxonomy_lookup()
    canonical = lookup.get(raw.lower().strip())

    if canonical:
        return canonical

    # Word-boundary partial match — avoid false positives from substring
    # containment (e.g. 'r' in 'react developer').  Only match if the
    # alias is a whole word within the input.
    import re
    raw_lower = raw.lower().strip()
    for alias, canon in lookup.items():
        if len(alias) < 2:
            # Single-char aliases (e.g. 'r', 'c') must be exact match only
            continue
        if re.search(r'\b' + re.escape(alias) + r'\b', raw_lower):
            return canon

    return None


def normalise_skills_batch(raw_skills: list[str]) -> list[dict]:
    """
    Normalise a list of raw skill strings.
    Returns list of {raw, canonical, matched} dicts.
    """
    results = []
    seen = set()

    for raw in raw_skills:
        canonical = normalise_skill(raw)
        key = canonical or raw.lower().strip()
        if key not in seen:
            seen.add(key)
            results.append({
                'raw': raw,
                'canonical': canonical or raw.lower().strip(),
                'matched': canonical is not None,
            })

    return results


def build_spacy_patterns() -> list[dict]:
    """
    Build spaCy EntityRuler patterns from the skill taxonomy.
    Returns list of patterns suitable for `ruler.add_patterns()`.
    """
    patterns = []
    lookup = get_taxonomy_lookup()
    seen_labels = set()

    for alias, canonical in lookup.items():
        label = f'SKILL'
        tokens = alias.split()

        if len(tokens) == 1:
            pattern = {'label': label, 'pattern': alias, 'id': canonical}
        else:
            pattern = {
                'label': label,
                'pattern': [{'LOWER': t.lower()} for t in tokens],
                'id': canonical,
            }

        pattern_key = f'{canonical}:{alias}'
        if pattern_key not in seen_labels:
            seen_labels.add(pattern_key)
            patterns.append(pattern)

    return patterns


def seed_taxonomy_from_constants():
    """
    Seed the SkillTaxonomy table from INITIAL_SKILLS constants.
    Idempotent — skips existing entries.
    """
    from intelligence.models import SkillTaxonomy

    created = 0
    for canonical, category, aliases in INITIAL_SKILLS:
        _, was_created = SkillTaxonomy.objects.get_or_create(
            canonical_name=canonical,
            defaults={
                'category': category,
                'aliases': aliases,
                'is_verified': True,
            },
        )
        if was_created:
            created += 1

    cache.delete(_CACHE_KEY)
    logger.info('Seeded %d new skills into taxonomy', created)
    return created


def update_usage_counts():
    """Update usage_count for all skills based on current profiles and jobs."""
    from collections import Counter
    from accounts.models import TalentProfile
    from jobs.models import JobPost
    from intelligence.models import SkillTaxonomy

    lookup = get_taxonomy_lookup()
    counter = Counter()

    # Count from talent profiles
    for skills in TalentProfile.objects.values_list('skills', flat=True):
        if skills:
            for s in skills:
                canonical = lookup.get(s.lower().strip(), s.lower().strip())
                counter[canonical] += 1

    # Count from jobs
    for skills in JobPost.objects.filter(status='open').values_list('skills_required', flat=True):
        if skills:
            for s in skills:
                canonical = lookup.get(s.lower().strip(), s.lower().strip())
                counter[canonical] += 1

    # Batch update — avoids N+1 individual saves
    updated = 0
    skills_to_update = []
    for skill in SkillTaxonomy.objects.all():
        new_count = counter.get(skill.canonical_name, 0)
        if skill.usage_count != new_count:
            skill.usage_count = new_count
            skills_to_update.append(skill)
            updated += 1

    if skills_to_update:
        SkillTaxonomy.objects.bulk_update(skills_to_update, ['usage_count'], batch_size=200)

    cache.delete(_CACHE_KEY)
    logger.info('Updated usage counts for %d skills', updated)
    return updated
