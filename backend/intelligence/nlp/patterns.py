"""
intelligence/nlp/patterns.py
Regex + spaCy patterns for entity extraction from resumes.
"""

import re

# ─── Date Patterns ────────────────────────────────────────────────────────────

MONTH_NAMES = (
    r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
    r'Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
)

# "Jan 2020 - Mar 2023", "January 2020 – Present", "2019-2023"
DATE_RANGE_PATTERN = re.compile(
    rf'({MONTH_NAMES}[\s,]*\d{{4}}|(?:0?[1-9]|1[0-2])/\d{{4}}|\d{{4}})'
    r'\s*[\–\-—to]+\s*'
    rf'({MONTH_NAMES}[\s,]*\d{{4}}|(?:0?[1-9]|1[0-2])/\d{{4}}|\d{{4}}|[Pp]resent|[Cc]urrent)',
    re.IGNORECASE,
)

# Standalone year: "2020"
YEAR_PATTERN = re.compile(r'\b((?:19|20)\d{2})\b')

# Graduation year near degree mentions
GRADUATION_YEAR = re.compile(
    r'(?:graduated?|class\s+of|expected)\s*:?\s*((?:19|20)\d{2})',
    re.IGNORECASE,
)

# ─── Degree Patterns ─────────────────────────────────────────────────────────

DEGREE_PATTERNS = re.compile(
    r'\b('
    r'Ph\.?D\.?|Doctor(?:ate)?(?:\s+of\s+\w+)?|'
    r'M\.?B\.?A\.?|'
    r'M\.?S\.?(?:c\.?)?|Master(?:\'?s)?(?:\s+of\s+\w+)?|M\.A\.?|'
    r'B\.?S\.?(?:c\.?)?|Bachelor(?:\'?s)?(?:\s+of\s+\w+)?|B\.A\.?|B\.E\.?|B\.Tech\.?|'
    r'Associate(?:\'?s)?(?:\s+(?:of|in)\s+\w+)?|A\.S\.?|A\.A\.?|'
    r'Diploma|Certificate|Certification'
    r')\b',
    re.IGNORECASE,
)

# ─── Job Title Patterns ──────────────────────────────────────────────────────

JOB_TITLE_KEYWORDS = re.compile(
    r'\b(?:'
    r'(?:Senior|Junior|Lead|Principal|Staff|Chief|Head\s+of|Director\s+of|VP\s+of|'
    r'Associate|Assistant|Manager|Coordinator|Specialist|Analyst|Consultant|'
    r'Intern|Trainee|Fellow)\s+)?'
    r'(?:Software|Web|Frontend|Front[\-\s]End|Backend|Back[\-\s]End|Full[\-\s]?Stack|'
    r'Mobile|iOS|Android|DevOps|Cloud|Data|Machine\s+Learning|ML|AI|'
    r'QA|Quality\s+Assurance|Test|Security|Network|System|Database|'
    r'Product|Project|Program|Engineering|Technical|IT|UX|UI|Design|'
    r'Marketing|Sales|Business|Operations|Finance|HR|Human\s+Resources)\s*'
    r'(?:Engineer|Developer|Architect|Designer|Scientist|Analyst|Manager|'
    r'Administrator|Specialist|Consultant|Lead|Director|Officer|Coordinator|'
    r'Tester|Researcher|Strategist|Executive)?'
    r'\b',
    re.IGNORECASE,
)

# ─── Contact Info Patterns ────────────────────────────────────────────────────

EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'
)

PHONE_PATTERN = re.compile(
    r'(?:\+?\d{1,3}[\s\-\.]?)?\(?\d{2,4}\)?[\s\-\.]?\d{3,4}[\s\-\.]?\d{3,4}'
)

LINKEDIN_PATTERN = re.compile(
    r'(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-]+/?',
    re.IGNORECASE,
)

GITHUB_PATTERN = re.compile(
    r'(?:https?://)?(?:www\.)?github\.com/[\w\-]+/?',
    re.IGNORECASE,
)

PORTFOLIO_PATTERN = re.compile(
    r'(?:https?://)?(?:www\.)?[\w\-]+\.(?:com|io|dev|me|org|net)(?:/[\w\-]*)*',
    re.IGNORECASE,
)


# ─── Month Name → Number Mapping ─────────────────────────────────────────────

MONTH_MAP = {
    'jan': 1, 'january': 1, 'feb': 2, 'february': 2,
    'mar': 3, 'march': 3, 'apr': 4, 'april': 4,
    'may': 5, 'jun': 6, 'june': 6,
    'jul': 7, 'july': 7, 'aug': 8, 'august': 8,
    'sep': 9, 'sept': 9, 'september': 9,
    'oct': 10, 'october': 10, 'nov': 11, 'november': 11,
    'dec': 12, 'december': 12,
}


def parse_date_string(date_str: str) -> dict | None:
    """
    Parse a date string into {year, month} dict.
    Returns None if parsing fails.
    """
    if not date_str:
        return None

    date_str = date_str.strip().lower()

    if date_str in ('present', 'current', 'now'):
        from datetime import date
        today = date.today()
        return {'year': today.year, 'month': today.month}

    # Try "Month Year" format
    for month_name, month_num in MONTH_MAP.items():
        if month_name in date_str:
            year_match = re.search(r'((?:19|20)\d{2})', date_str)
            if year_match:
                return {'year': int(year_match.group(1)), 'month': month_num}

    # Try "MM/YYYY" format
    mm_yyyy = re.match(r'(\d{1,2})/(\d{4})', date_str)
    if mm_yyyy:
        return {'year': int(mm_yyyy.group(2)), 'month': int(mm_yyyy.group(1))}

    # Try standalone year
    year_match = re.match(r'^((?:19|20)\d{2})$', date_str)
    if year_match:
        return {'year': int(year_match.group(1)), 'month': 1}

    return None


def calculate_duration_months(start: dict, end: dict) -> int:
    """Calculate duration in months between two date dicts."""
    if not start or not end:
        return 0

    start_months = start['year'] * 12 + start.get('month', 1)
    end_months = end['year'] * 12 + end.get('month', 12)
    return max(0, end_months - start_months)
