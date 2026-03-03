"""
intelligence/nlp/parser.py
Main resume parsing orchestrator.

Coordinates text extraction, normalisation, NLP processing, and structured output.
"""

import hashlib
import logging
import time

from intelligence.constants import BIO_MAX_LENGTH, PARSER_VERSION

logger = logging.getLogger(__name__)


def _extract_text_from_file(file_obj) -> str:
    """Extract plain text from PDF, DOCX, or TXT file."""
    filename = getattr(file_obj, 'name', '')
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    if ext == 'pdf':
        return _extract_pdf(file_obj)
    elif ext == 'docx':
        return _extract_docx(file_obj)
    elif ext == 'doc':
        raise ValueError(
            'Legacy .doc format is not supported. Please convert to .docx or PDF.'
        )
    elif ext == 'txt':
        content = file_obj.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='replace')
        return content
    else:
        raise ValueError(f'Unsupported file format: {ext}')


def _extract_pdf(file_obj) -> str:
    """Extract text from a PDF file using PyPDF2."""
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(file_obj)
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return '\n'.join(pages)
    except Exception as exc:
        raise ValueError(f'Failed to read PDF file: {exc}') from exc


def _extract_docx(file_obj) -> str:
    """Extract text from a DOCX file."""
    try:
        from docx import Document

        doc = Document(file_obj)
        paragraphs = []
        for para in doc.paragraphs:
            if para.text.strip():
                paragraphs.append(para.text)
        return '\n'.join(paragraphs)
    except Exception as exc:
        raise ValueError(f'Failed to read DOCX file: {exc}') from exc


def _compute_file_hash(file_obj) -> str:
    """Compute SHA-256 hash of file contents."""
    file_obj.seek(0)
    content = file_obj.read()
    file_obj.seek(0)
    if isinstance(content, str):
        content = content.encode('utf-8')
    return hashlib.sha256(content).hexdigest()


def _generate_bio(skills: list[dict], experience: list[dict], total_years: float) -> str:
    """Generate a brief professional bio from extracted data."""
    parts = []

    if total_years and total_years > 0:
        years_str = f'{total_years:.0f}' if total_years == int(total_years) else f'{total_years:.1f}'
        parts.append(f'{years_str} years of experience')

    if skills:
        top_skills = [s['canonical_name'] for s in skills[:5]]
        parts.append('skilled in ' + ', '.join(top_skills))

    if experience:
        latest = experience[0]
        if latest.get('title'):
            parts.append(f'most recently as {latest["title"]}')
            if latest.get('company'):
                parts[-1] += f' at {latest["company"]}'

    if not parts:
        return ''

    bio = 'Professional with ' + '. '.join(parts) + '.'
    return bio[:BIO_MAX_LENGTH]


def _calculate_total_experience(experience: list[dict]) -> float:
    """Calculate total years of experience from parsed entries."""
    total_months = sum(
        entry.get('duration_months', 0)
        for entry in experience
        if entry.get('duration_months')
    )
    return round(total_months / 12.0, 1) if total_months > 0 else 0.0


def _compute_confidence(skills: list[dict], experience: list[dict], education: list[dict]) -> float:
    """Compute overall parsing confidence (0-1)."""
    score = 0.0

    # Skills contribute up to 0.4
    if skills:
        avg_skill_conf = sum(s['confidence'] for s in skills) / len(skills)
        score += min(0.4, avg_skill_conf * 0.4)

    # Experience contributes up to 0.35
    if experience:
        exp_with_dates = sum(1 for e in experience if e.get('start_date'))
        score += min(0.35, (exp_with_dates / max(len(experience), 1)) * 0.35)

    # Education contributes up to 0.25
    if education:
        edu_with_degree = sum(1 for e in education if e.get('degree'))
        score += min(0.25, (edu_with_degree / max(len(education), 1)) * 0.25)

    return round(score, 2)


def parse_resume(file_obj, user=None) -> dict:
    """
    Main resume parsing pipeline.
    Returns a structured dict with all extracted data.
    Optionally saves to ParsedResume model if user is provided.
    """
    start = time.monotonic()

    # 1. Compute file hash (skip re-parse if identical)
    file_hash = _compute_file_hash(file_obj)

    if user:
        try:
            from intelligence.models import ParsedResume
            existing = ParsedResume.objects.filter(user=user).first()
            if existing and existing.source_file_hash == file_hash:
                logger.info('Resume unchanged (hash match), returning cached parse')
                return {
                    'skills': existing.parsed_skills,
                    'experience': existing.parsed_experience,
                    'education': existing.parsed_education,
                    'total_experience_years': existing.total_experience_years,
                    'bio': existing.generated_bio,
                    'contact': existing.contact_info,
                    'confidence_score': existing.confidence_score,
                    'parser_version': existing.parser_version,
                    'cached': True,
                }
        except Exception:
            logger.warning(
                'Cache-check for parsed resume failed for user %s', user.id,
                exc_info=True,
            )

    # 2. Extract raw text
    raw_text = _extract_text_from_file(file_obj)

    # 3. Normalise
    from intelligence.nlp.normalizer import normalize_text, detect_sections
    clean_text = normalize_text(raw_text)

    # 4. Detect sections
    sections = detect_sections(clean_text)

    # 5. Extract skills from each section
    from intelligence.nlp.extractors import (
        extract_contact_info,
        extract_education,
        extract_experience,
        extract_skills,
    )

    all_skills = []
    seen_skills = set()

    # Prioritise explicit skills section
    if 'skills' in sections:
        for s in extract_skills(sections['skills'], 'skills'):
            if s['canonical_name'] not in seen_skills:
                seen_skills.add(s['canonical_name'])
                all_skills.append(s)

    # Then experience section
    if 'experience' in sections:
        for s in extract_skills(sections['experience'], 'experience'):
            if s['canonical_name'] not in seen_skills:
                seen_skills.add(s['canonical_name'])
                all_skills.append(s)

    # Then full text for anything missed
    for s in extract_skills(clean_text, 'full'):
        if s['canonical_name'] not in seen_skills:
            seen_skills.add(s['canonical_name'])
            all_skills.append(s)

    # 6. Extract experience
    exp_text = sections.get('experience', clean_text)
    experience = extract_experience(exp_text)

    # 7. Extract education
    edu_text = sections.get('education', clean_text)
    education = extract_education(edu_text)

    # 8. Extract contact info
    # Prefer header/contact sections; fall back to full text if both are empty
    header_text = (
        sections.get('header', '') + '\n' + sections.get('contact', '')
    ).strip()
    contact = extract_contact_info(header_text or clean_text)

    # 9. Calculate totals
    total_years = _calculate_total_experience(experience)

    # 10. Generate bio
    bio = _generate_bio(all_skills, experience, total_years)

    # 11. Confidence
    confidence = _compute_confidence(all_skills, experience, education)

    result = {
        'skills': all_skills,
        'experience': experience,
        'education': education,
        'total_experience_years': total_years,
        'bio': bio,
        'contact': contact,
        'raw_text': clean_text,
        'confidence_score': confidence,
        'parser_version': PARSER_VERSION,
        'cached': False,
    }

    # 12. Persist if user provided
    if user:
        try:
            from intelligence.models import ParsedResume
            ParsedResume.objects.update_or_create(
                user=user,
                defaults={
                    'raw_text': clean_text,
                    'parsed_skills': all_skills,
                    'parsed_experience': experience,
                    'parsed_education': education,
                    'total_experience_years': total_years,
                    'generated_bio': bio,
                    'contact_info': contact,
                    'confidence_score': confidence,
                    'parser_version': PARSER_VERSION,
                    'source_file_hash': file_hash,
                },
            )
        except Exception:
            logger.error('Failed to save ParsedResume', exc_info=True)

    elapsed = int((time.monotonic() - start) * 1000)
    logger.info('Resume parsed in %dms (confidence=%.2f, skills=%d)', elapsed, confidence, len(all_skills))

    return result
