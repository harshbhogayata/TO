"""intelligence.nlp — NLP-based resume parsing and skill extraction.

Public API (import from submodules directly)::

    from intelligence.nlp.parser import parse_resume
    from intelligence.nlp.taxonomy import normalise_skill, normalise_skills_batch
"""

__all__ = [
    'parser',
    'extractors',
    'taxonomy',
    'normalizer',
    'patterns',
]