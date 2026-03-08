"""
AI-enhanced resume parsing combining traditional NLP with optional OpenAI enrichment.
"""

import json
import logging
import re
import time
from typing import Dict

from .extractors import extract_contact_info, extract_education, extract_experience
from .normalizer import detect_sections, normalize_text
from .parser import (
    _compute_file_hash,
    _extract_docx,
    _extract_pdf,
    _generate_bio,
    _calculate_total_experience,
    _compute_confidence,
    parse_resume as parse_resume_nlp,
)

logger = logging.getLogger(__name__)

_EMAIL_PATTERN = re.compile(r'(?P<email>[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})', re.IGNORECASE)
_PHONE_PATTERN = re.compile(r'(?P<phone>(?:\+?\d[\d().\-\s]{7,}\d))')
_MAX_PROMPT_CHARS = 12000


def _truncate_for_prompt(text: str, limit: int = _MAX_PROMPT_CHARS) -> str:
    text = text or ''
    if len(text) <= limit:
        return text
    return text[:limit]


def _redact_pii_for_ai(text: str) -> tuple[str, Dict[str, int]]:
    """Remove obvious direct identifiers before sending text to the model."""
    redactions = {'emails': 0, 'phones': 0}

    def _replace_email(match):
        redactions['emails'] += 1
        return '[REDACTED_EMAIL]'

    def _replace_phone(match):
        redactions['phones'] += 1
        return '[REDACTED_PHONE]'

    text = _EMAIL_PATTERN.sub(_replace_email, text or '')
    text = _PHONE_PATTERN.sub(_replace_phone, text)
    return text, redactions


def call_openai_with_fallback(prompt: str, *, max_tokens: int = 1200, temperature: float = 0.1):
    """Return parsed JSON from OpenAI, or None when AI is unavailable."""
    from django.conf import settings

    api_key = getattr(settings, 'OPENAI_API_KEY', '')
    model = getattr(settings, 'OPENAI_MODEL', 'gpt-4o-mini')

    if not api_key:
        logger.info('OpenAI API key is not configured; using NLP-only resume parsing fallback')
        return None

    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'You are an expert resume parsing assistant. '
                        'Return valid JSON only, with no surrounding commentary.'
                    ),
                },
                {'role': 'user', 'content': prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={'type': 'json_object'},
        )
        content = response.choices[0].message.content or '{}'
        return json.loads(content)
    except Exception as exc:
        logger.warning('OpenAI resume enrichment unavailable; falling back to NLP extraction: %s', exc)
        return None


def extract_skills_with_ai(text: str, section_text: str = '') -> tuple[list[dict], bool]:
    """Enhanced skill extraction using AI for contextual understanding."""
    from .extractors import extract_skills as extract_skills_nlp

    baseline_text = section_text or text
    baseline_section = 'skills' if section_text else 'full'
    nlp_skills = extract_skills_nlp(baseline_text, baseline_section)

    prompt = f"""
Extract technical and professional skills from the following resume content.
Return JSON with this shape only:
{{
  "skills": [
    {{"name": "React", "canonical_name": "react", "confidence": 0.92, "source": "ai_enhanced"}}
  ]
}}

Rules:
- Include only skills explicitly evidenced in the text.
- Prefer technical and domain skills over generic soft skills.
- Use lowercase canonical_name values.
- Confidence must be between 0.0 and 1.0.

Resume content:
{_truncate_for_prompt(baseline_text)}
"""

    ai_result = call_openai_with_fallback(prompt)
    if not ai_result:
        return nlp_skills, False

    ai_skills = ai_result.get('skills') or []
    if not isinstance(ai_skills, list):
        logger.warning('AI skills response was not a list; using NLP-only skill extraction')
        return nlp_skills, False

    seen = set()
    merged = []
    used_ai = False

    for skill in ai_skills:
        if not isinstance(skill, dict):
            continue
        canonical_name = str(skill.get('canonical_name') or skill.get('name') or '').strip().lower()
        if not canonical_name or canonical_name in seen:
            continue
        seen.add(canonical_name)
        merged.append({
            'name': str(skill.get('name') or canonical_name),
            'canonical_name': canonical_name,
            'confidence': max(0.0, min(float(skill.get('confidence', 0.7)), 1.0)),
            'source': 'ai_enhanced',
        })
        used_ai = True

    for skill in nlp_skills:
        canonical_name = str(skill.get('canonical_name', '')).strip().lower()
        if not canonical_name or canonical_name in seen:
            continue
        seen.add(canonical_name)
        merged.append(skill)

    merged.sort(key=lambda item: item.get('confidence', 0), reverse=True)
    return merged, used_ai


def extract_experience_with_ai(text: str, experience_text: str) -> tuple[list[dict], bool]:
    """Enhanced experience extraction using AI for structured chronology."""
    baseline = extract_experience(experience_text or text)
    prompt = f"""
Extract work experience from the following resume content.
Return JSON with this shape only:
{{
  "experience": [
    {{
      "title": "Software Engineer",
      "company": "Tech Corp",
      "start_date": "2021-01",
      "end_date": "Present",
      "description": "Built internal tooling",
      "duration_months": 24
    }}
  ]
}}

Use null or empty strings instead of inventing data.
Resume content:
{_truncate_for_prompt(experience_text or text)}
"""

    ai_result = call_openai_with_fallback(prompt)
    if not ai_result:
        return baseline, False

    ai_experience = ai_result.get('experience') or []
    if not isinstance(ai_experience, list):
        logger.warning('AI experience response was not a list; using NLP-only experience extraction')
        return baseline, False

    cleaned = [item for item in ai_experience if isinstance(item, dict)]
    return cleaned or baseline, bool(cleaned)


def extract_education_with_ai(text: str, education_text: str) -> tuple[list[dict], bool]:
    """Enhanced education extraction using AI for degree normalization."""
    baseline = extract_education(education_text or text)
    prompt = f"""
Extract education entries from the following resume content.
Return JSON with this shape only:
{{
  "education": [
    {{
      "degree": "Bachelor of Science",
      "institution": "University Name",
      "field": "Computer Science",
      "graduation_year": "2020",
      "gpa": "3.8"
    }}
  ]
}}

Use null or empty strings instead of inventing data.
Resume content:
{_truncate_for_prompt(education_text or text)}
"""

    ai_result = call_openai_with_fallback(prompt)
    if not ai_result:
        return baseline, False

    ai_education = ai_result.get('education') or []
    if not isinstance(ai_education, list):
        logger.warning('AI education response was not a list; using NLP-only education extraction')
        return baseline, False

    cleaned = [item for item in ai_education if isinstance(item, dict)]
    return cleaned or baseline, bool(cleaned)


def parse_resume_ai_enhanced(file_obj, user=None) -> dict:
    """AI-enhanced resume parsing pipeline with safe fallbacks."""
    start_time = time.monotonic()
    file_hash = _compute_file_hash(file_obj)

    if user:
        try:
            from intelligence.models import ParsedResume

            existing = ParsedResume.objects.filter(user=user).first()
            if existing and existing.source_file_hash == file_hash:
                logger.info('AI-enhanced parser cache hit for user %s', user.id)
                return {
                    'parsed_skills': existing.parsed_skills,
                    'parsed_experience': existing.parsed_experience,
                    'parsed_education': existing.parsed_education,
                    'total_experience_years': existing.total_experience_years,
                    'generated_bio': existing.generated_bio,
                    'contact_info': existing.contact_info,
                    'confidence_score': existing.confidence_score,
                    'parser_version': existing.parser_version,
                    'source_file_hash': existing.source_file_hash,
                    'raw_text': existing.raw_text,
                    'cached': True,
                    'ai_enhanced': str(existing.parser_version).startswith('ai_enhanced'),
                }
        except Exception:
            logger.warning('AI-enhanced parser cache check failed for user %s', user.id, exc_info=True)

    try:
        raw_text = _extract_text_from_file(file_obj)
        clean_text = normalize_text(raw_text)
        sections = detect_sections(clean_text)

        redacted_text, redactions = _redact_pii_for_ai(clean_text)
        redacted_sections = {
            name: _redact_pii_for_ai(section_text)[0]
            for name, section_text in sections.items()
        }

        skills, skills_used_ai = extract_skills_with_ai(
            redacted_text,
            redacted_sections.get('skills', ''),
        )
        experience, experience_used_ai = extract_experience_with_ai(
            redacted_text,
            redacted_sections.get('experience', ''),
        )
        education, education_used_ai = extract_education_with_ai(
            redacted_text,
            redacted_sections.get('education', ''),
        )

        contact_source = (
            sections.get('header', '') + '\n' + sections.get('contact', '')
        ).strip() or clean_text
        contact = extract_contact_info(contact_source)
        total_years = _calculate_total_experience(experience)
        bio = _generate_bio(skills, experience, total_years)
        confidence = _compute_confidence(skills, experience, education)

        ai_enhanced = skills_used_ai or experience_used_ai or education_used_ai
        parser_version = 'ai_enhanced_v1' if ai_enhanced else 'spacy_v1'

        result = {
            'skills': skills,
            'experience': experience,
            'education': education,
            'total_experience_years': total_years,
            'bio': bio,
            'contact': contact,
            'raw_text': clean_text,
            'confidence_score': confidence,
            'parser_version': parser_version,
            'source_file_hash': file_hash,
            'cached': False,
            'ai_enhanced': ai_enhanced,
            'extraction_time_ms': int((time.monotonic() - start_time) * 1000),
        }

        if user:
            _persist_parsed_resume(user, result)

        logger.info(
            'Resume parsed via %s in %dms (skills=%d, experience=%d, education=%d, redacted_emails=%d, redacted_phones=%d)',
            parser_version,
            result['extraction_time_ms'],
            len(skills),
            len(experience),
            len(education),
            redactions['emails'],
            redactions['phones'],
        )
        return result
    except Exception:
        logger.exception('AI-enhanced resume parsing failed; falling back to traditional parser')
        return parse_resume_nlp(file_obj, user)


def _extract_text_from_file(file_obj) -> str:
    """Extract text from PDF, DOCX, or TXT files."""
    filename = getattr(file_obj, 'name', '')
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    if ext == 'pdf':
        return _extract_pdf(file_obj)
    if ext == 'docx':
        return _extract_docx(file_obj)
    if ext == 'txt':
        content = file_obj.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='replace')
        return content
    raise ValueError(f'Unsupported file format: {ext}')


def _persist_parsed_resume(user, result: dict):
    """Persist parsed resume results using the canonical model fields."""
    try:
        from intelligence.models import ParsedResume

        ParsedResume.objects.update_or_create(
            user=user,
            defaults={
                'raw_text': result['raw_text'],
                'parsed_skills': result['skills'],
                'parsed_experience': result['experience'],
                'parsed_education': result['education'],
                'total_experience_years': result['total_experience_years'],
                'generated_bio': result['bio'],
                'contact_info': result['contact'],
                'confidence_score': result['confidence_score'],
                'parser_version': result['parser_version'],
                'source_file_hash': result['source_file_hash'],
            },
        )
    except Exception:
        logger.exception('Failed to persist AI-enhanced parsed resume for user %s', user.id)
