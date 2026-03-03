"""
intelligence/nlp/normalizer.py
Text cleaning, unicode normalisation, and section boundary detection for resumes.
"""

import re
import unicodedata


def normalize_text(text: str) -> str:
    """Clean and normalise raw resume text."""
    if not text:
        return ''

    # Unicode normalisation (NFC — composed form)
    text = unicodedata.normalize('NFC', text)

    # Replace common ligatures
    ligatures = {'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬀ': 'ff', 'ﬃ': 'ffi', 'ﬄ': 'ffl'}
    for lig, replacement in ligatures.items():
        text = text.replace(lig, replacement)

    # Normalise whitespace (tabs, multiple spaces → single space)
    text = re.sub(r'[ \t]+', ' ', text)

    # Normalise line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Remove page headers/footers (common in PDFs)
    text = re.sub(r'Page \d+ of \d+', '', text, flags=re.IGNORECASE)

    # Remove excessive blank lines (keep max 2)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


# ─── Section Detection ────────────────────────────────────────────────────────

# Patterns for detecting resume section headings
SECTION_PATTERNS = {
    'skills': re.compile(
        r'^(?:technical\s+)?skills?(?:\s+(?:&|and)\s+\w+)?(?:\s*:?\s*)$',
        re.IGNORECASE | re.MULTILINE,
    ),
    'experience': re.compile(
        r'^(?:work\s+|professional\s+)?experience(?:\s*:?\s*)$',
        re.IGNORECASE | re.MULTILINE,
    ),
    'education': re.compile(
        r'^education(?:al\s+background)?(?:\s*:?\s*)$',
        re.IGNORECASE | re.MULTILINE,
    ),
    'summary': re.compile(
        r'^(?:professional\s+)?(?:summary|objective|profile|about\s+me)(?:\s*:?\s*)$',
        re.IGNORECASE | re.MULTILINE,
    ),
    'projects': re.compile(
        r'^(?:personal\s+|key\s+)?projects?(?:\s*:?\s*)$',
        re.IGNORECASE | re.MULTILINE,
    ),
    'certifications': re.compile(
        r'^(?:certifications?|licenses?)(?:\s+(?:&|and)\s+\w+)?(?:\s*:?\s*)$',
        re.IGNORECASE | re.MULTILINE,
    ),
    'contact': re.compile(
        r'^contact(?:\s+(?:info|information|details))?(?:\s*:?\s*)$',
        re.IGNORECASE | re.MULTILINE,
    ),
}

# Broader heading detection for any capitalised line that looks like a heading
GENERIC_HEADING = re.compile(
    r'^[A-Z][A-Z\s&/]{2,}(?:\s*:?\s*)$',
    re.MULTILINE,
)


def detect_sections(text: str) -> dict[str, str]:
    """
    Split resume text into named sections.
    Returns {section_name: section_text} dict.
    """
    if not text:
        return {}

    # Find all section heading positions
    headings = []  # (position, section_name)

    for section_name, pattern in SECTION_PATTERNS.items():
        for match in pattern.finditer(text):
            headings.append((match.start(), match.end(), section_name))

    if not headings:
        # No detected sections → entire text is 'full'
        return {'full': text}

    headings.sort(key=lambda x: x[0])

    # Extract text between headings
    sections = {}
    for i, (start, end, name) in enumerate(headings):
        if i + 1 < len(headings):
            section_text = text[end:headings[i + 1][0]]
        else:
            section_text = text[end:]

        sections[name] = section_text.strip()

    # Also capture text before the first heading as 'header'
    if headings[0][0] > 0:
        sections['header'] = text[:headings[0][0]].strip()

    return sections


def normalize_bullet_points(text: str) -> list[str]:
    """Extract individual bullet points / list items from text."""
    if not text:
        return []

    # Split on common bullet patterns
    lines = re.split(r'\n\s*[•●◦▪▸►\-\*]\s*|\n\s*\d+[\.\)]\s*', text)
    items = [line.strip() for line in lines if line.strip()]
    return items
