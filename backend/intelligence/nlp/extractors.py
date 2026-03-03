"""
intelligence/nlp/extractors.py
Skill, education, and experience extractors using spaCy NER + custom patterns.
"""

import logging
import re
from typing import Optional

from intelligence.constants import MIN_SKILL_CONFIDENCE
from intelligence.nlp.patterns import (
    DATE_RANGE_PATTERN,
    DEGREE_PATTERNS,
    GRADUATION_YEAR,
    JOB_TITLE_KEYWORDS,
    calculate_duration_months,
    parse_date_string,
)
from intelligence.nlp.taxonomy import get_taxonomy_lookup

logger = logging.getLogger(__name__)


def extract_skills(text: str, section_name: str = 'full') -> list[dict]:
    """
    Extract skills from text using taxonomy matching.
    Returns list of {name, canonical_name, confidence, source} dicts.
    """
    if not text:
        return []

    lookup = get_taxonomy_lookup()
    text_lower = text.lower()
    found = []
    seen = set()

    # Confidence weight based on section
    section_confidence = {
        'skills': 1.0,
        'full': 0.6,
        'experience': 0.7,
        'summary': 0.6,
        'projects': 0.7,
        'header': 0.5,
    }
    base_confidence = section_confidence.get(section_name, 0.5)

    # Match against taxonomy
    for alias, canonical in lookup.items():
        if canonical in seen:
            continue

        # Word-boundary match to avoid partial matches
        pattern = re.compile(r'\b' + re.escape(alias) + r'\b', re.IGNORECASE)
        matches = pattern.findall(text)

        if matches:
            # Boost confidence by frequency
            freq_boost = min(0.2, len(matches) * 0.05)
            confidence = min(1.0, base_confidence + freq_boost)

            if confidence >= MIN_SKILL_CONFIDENCE:
                seen.add(canonical)
                found.append({
                    'name': matches[0],
                    'canonical_name': canonical,
                    'confidence': round(confidence, 2),
                    'source': section_name,
                })

    # Sort by confidence descending
    found.sort(key=lambda x: -x['confidence'])
    return found


def extract_experience(text: str) -> list[dict]:
    """
    Extract work experience entries from the experience section.
    Returns list of {title, company, start_date, end_date, duration_months, description} dicts.
    """
    if not text:
        return []

    entries = []
    lines = text.split('\n')

    current_entry = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for job title
        title_match = JOB_TITLE_KEYWORDS.search(line)

        # Check for date range
        date_match = DATE_RANGE_PATTERN.search(line)

        if title_match and (date_match or _looks_like_title_line(line)):
            # Save previous entry
            if current_entry:
                entries.append(current_entry)

            title = title_match.group(0).strip()
            company = _extract_company_from_line(line, title)

            start_date = None
            end_date = None
            duration = 0

            if date_match:
                start_date = parse_date_string(date_match.group(1))
                end_date = parse_date_string(date_match.group(2))
                duration = calculate_duration_months(start_date, end_date)

            current_entry = {
                'title': title,
                'company': company,
                'start_date': _format_date(start_date),
                'end_date': _format_date(end_date),
                'duration_months': duration,
                'description': '',
            }
        elif current_entry:
            # Accumulate description lines
            if current_entry['description']:
                current_entry['description'] += '\n'
            current_entry['description'] += line

    if current_entry:
        entries.append(current_entry)

    return entries


def extract_education(text: str) -> list[dict]:
    """
    Extract education entries.
    Returns list of {degree, institution, field, graduation_year} dicts.
    """
    if not text:
        return []

    entries = []
    lines = text.split('\n')

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        degree_match = DEGREE_PATTERNS.search(line)
        if not degree_match:
            continue

        degree = degree_match.group(0).strip()

        # Try to find institution (typically on same or next line)
        institution = ''
        context = line
        if i + 1 < len(lines):
            context += ' ' + lines[i + 1].strip()

        # Remove the degree part to find the institution
        remaining = line[degree_match.end():].strip()
        if remaining.startswith(('in ', 'of ', '- ', '— ', ', ')):
            parts = re.split(r'\s+(?:at|from|,)\s+', remaining, maxsplit=1)
            if len(parts) > 1:
                institution = parts[1].strip()
            else:
                # Strip leading prepositions/separators as substrings, not chars
                institution = re.sub(
                    r'^(?:in|of|\s|[-—,])+', '', remaining,
                ).strip()
        elif remaining:
            institution = re.sub(r'^[-—,\s]+', '', remaining).strip()

        # Look for field of study
        field_match = re.search(
            r'(?:in|of)\s+(.+?)(?:\s*[\-—,]|\s+at\s+|\s*$)',
            line[degree_match.end():],
            re.IGNORECASE,
        )
        field_of_study = field_match.group(1).strip() if field_match else ''

        # Graduation year
        grad_year = None
        grad_match = GRADUATION_YEAR.search(context)
        if grad_match:
            grad_year = int(grad_match.group(1))
        else:
            from intelligence.nlp.patterns import YEAR_PATTERN
            year_matches = YEAR_PATTERN.findall(context)
            if year_matches:
                grad_year = int(year_matches[-1])

        entries.append({
            'degree': degree,
            'institution': institution[:200] if institution else '',
            'field': field_of_study[:200] if field_of_study else '',
            'graduation_year': grad_year,
        })

    return entries


def extract_contact_info(text: str) -> dict:
    """Extract contact information from resume text."""
    if not text:
        return {}

    from intelligence.nlp.patterns import (
        EMAIL_PATTERN,
        GITHUB_PATTERN,
        LINKEDIN_PATTERN,
        PHONE_PATTERN,
    )

    contact = {}

    email_match = EMAIL_PATTERN.search(text)
    if email_match:
        contact['email'] = email_match.group(0)

    phone_match = PHONE_PATTERN.search(text)
    if phone_match:
        contact['phone'] = phone_match.group(0).strip()

    linkedin_match = LINKEDIN_PATTERN.search(text)
    if linkedin_match:
        contact['linkedin'] = linkedin_match.group(0)

    github_match = GITHUB_PATTERN.search(text)
    if github_match:
        contact['github'] = github_match.group(0)

    return contact


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _looks_like_title_line(line: str) -> bool:
    """Heuristic: does this line look like a job title line?"""
    # Short lines with capitalised words often are titles
    words = line.split()
    if len(words) > 15:
        return False
    capitalised = sum(1 for w in words if w[0].isupper()) if words else 0
    return capitalised >= len(words) * 0.5


def _extract_company_from_line(line: str, title: str) -> str:
    """Try to extract company name from the same line as the title."""
    remaining = line.replace(title, '', 1).strip()

    # Remove date ranges
    remaining = DATE_RANGE_PATTERN.sub('', remaining).strip()

    # Remove common separators
    remaining = re.sub(r'^[\s\-—|,@]+|[\s\-—|,]+$', '', remaining)

    # Common patterns: "at Company" or "| Company" or "- Company"
    at_match = re.search(r'(?:at|@|,)\s+(.+?)(?:\s*[\-—|]|$)', remaining, re.IGNORECASE)
    if at_match:
        return at_match.group(1).strip()[:200]

    return remaining[:200] if remaining else ''


def _format_date(date_dict: Optional[dict]) -> Optional[str]:
    """Format a date dict as 'YYYY-MM' string."""
    if not date_dict:
        return None
    year = date_dict.get('year', '')
    month = date_dict.get('month', 1)
    return f'{year}-{month:02d}'
