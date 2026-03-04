"""
intelligence/ai_views.py
AI-powered features — job description generator, interview scheduler,
chatbot assistant, and compensation benchmarking.

Uses OpenAI's chat completion API for:
    - Job description generation from minimal inputs
    - Interview scheduling suggestions
    - Context-aware chatbot for job search assistance
    - Compensation benchmarking (role/location → salary ranges)

Enterprise patterns:
    - ScopedRateThrottle (ai_generate scope)
    - PII stripping before LLM calls (intelligence.pii_detector)
    - Prompt injection detection
    - Content moderation on AI responses
    - Audit logging on AI invocations
    - Circuit breaker for OpenAI API calls
    - Structured prompts with token limits
    - Graceful fallback on API errors
"""
import json
import logging

from django.conf import settings
from django.core.cache import cache
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from accounts.permissions import IsEmailVerified
from compliance.constants import AuditAction, AuditCategory
from compliance.decorators import audit_action
from intelligence.pii_detector import validate_ai_input, moderate_ai_response, strip_pii

logger = logging.getLogger(__name__)


class AIGenerateThrottle(ScopedRateThrottle):
    scope = 'ai_generate'


def _get_openai_client():
    """Get OpenAI client with circuit breaker protection."""
    import openai
    try:
        from talentorbit.circuit_breaker import get_breaker
        breaker = get_breaker('llm')
        breaker.check()
    except Exception:
        pass  # Circuit breaker not configured — proceed without it
    return openai.OpenAI(api_key=settings.OPENAI_API_KEY)


def _record_circuit_breaker_success():
    """Record a successful LLM call for circuit breaker."""
    try:
        from talentorbit.circuit_breaker import get_breaker
        get_breaker('llm').record_success()
    except Exception:
        pass


def _record_circuit_breaker_failure():
    """Record a failed LLM call for circuit breaker."""
    try:
        from talentorbit.circuit_breaker import get_breaker
        get_breaker('llm').record_failure()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# AI JOB DESCRIPTION WRITER
# ═══════════════════════════════════════════════════════════════════════════════

JOB_DESCRIPTION_SYSTEM_PROMPT = """You are TalentOrbit's AI writing assistant. Generate professional, engaging job descriptions.

Rules:
1. Write in clear, inclusive language. Avoid gender-coded words.
2. Structure the output as JSON with these keys:
   - "title": refined job title
   - "description": full job description (Markdown, 300-500 words)
   - "responsibilities": array of 5-8 bullet points
   - "requirements": array of 5-8 bullet points
   - "nice_to_have": array of 3-5 bullet points
   - "skills_required": array of 8-15 skill tags
   - "salary_suggestion": object with "min" and "max" (annual USD, based on market data)
3. Be specific and avoid generic filler text.
4. Match the tone to the company culture if described.
5. Always respond with valid JSON only, no markdown code fences."""


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsEmailVerified])
@throttle_classes([AIGenerateThrottle])
@audit_action(
    action=AuditAction.CREATE,
    category=AuditCategory.JOB,
    description='AI-generated job description',
    resource_type='intelligence.AIGeneration',
)
def ai_generate_job_description(request):
    """
    POST /api/v1/intelligence/ai/job-description/
    Body: {
        "title": "Senior Backend Engineer",
        "department": "Engineering",
        "work_mode": "remote",
        "job_type": "full_time",
        "experience_level": "senior",
        "company_description": "...",  (optional)
        "key_technologies": ["Python", "Django", "PostgreSQL"],  (optional)
        "additional_notes": "..."  (optional)
    }
    Returns: AI-generated structured job description.
    """
    if not settings.OPENAI_API_KEY:
        return Response(
            {'error': 'AI features are not configured. Please set OPENAI_API_KEY.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    title = request.data.get('title', '').strip()
    if not title:
        return Response(
            {'error': 'Job title is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Build user prompt from inputs
    user_prompt_parts = [f'Generate a job description for: {title}']

    field_map = {
        'department': 'Department',
        'work_mode': 'Work mode',
        'job_type': 'Employment type',
        'experience_level': 'Experience level',
        'company_description': 'Company context',
    }
    for field, label in field_map.items():
        value = request.data.get(field, '')
        if value:
            user_prompt_parts.append(f'{label}: {value}')

    key_technologies = request.data.get('key_technologies', [])
    if key_technologies:
        user_prompt_parts.append(f'Key technologies: {", ".join(key_technologies)}')

    additional_notes = request.data.get('additional_notes', '')
    if additional_notes:
        user_prompt_parts.append(f'Additional requirements: {additional_notes}')

    user_prompt = '\n'.join(user_prompt_parts)

    # ── PII stripping + prompt injection prevention ──
    try:
        user_prompt, detected_pii = validate_ai_input(user_prompt)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    if detected_pii:
        logger.info(
            'PII redacted from AI job description input: types=%s user=%s',
            detected_pii, request.user.id,
        )

    try:
        client = _get_openai_client()
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {'role': 'system', 'content': JOB_DESCRIPTION_SYSTEM_PROMPT},
                {'role': 'user', 'content': user_prompt},
            ],
            max_tokens=2000,
            temperature=0.7,
            response_format={'type': 'json_object'},
        )

        content = response.choices[0].message.content
        _record_circuit_breaker_success()

        # ── Content moderation on response ──
        content, is_safe = moderate_ai_response(content)
        if not is_safe:
            return Response(
                {'error': content},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        parsed = json.loads(content)

        return Response({
            'generated': parsed,
            'tokens_used': response.usage.total_tokens if response.usage else 0,
            'model': settings.OPENAI_MODEL,
        })

    except json.JSONDecodeError:
        logger.warning('AI returned non-JSON response')
        return Response({
            'generated': {'description': content, 'title': title},
            'tokens_used': 0,
            'model': settings.OPENAI_MODEL,
            'warning': 'Response was not structured JSON. Returning raw text.',
        })
    except Exception as e:
        _record_circuit_breaker_failure()
        logger.exception('AI job description generation failed')
        return Response(
            {'error': 'AI generation failed. Please try again.', 'detail': str(e)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# AI INTERVIEW SCHEDULER
# ═══════════════════════════════════════════════════════════════════════════════

INTERVIEW_SCHEDULER_PROMPT = """You are TalentOrbit's AI interview scheduling assistant.

Given candidate information and available time slots, generate an optimal interview schedule.

Rules:
1. Output valid JSON with these keys:
   - "schedule": array of interview objects with "date", "time", "duration_minutes", "type" (phone/video/onsite), "interviewer_role", "focus_area"
   - "preparation_tips": array of 3-5 tips for the candidate
   - "suggested_questions": array of 5-7 interview questions tailored to the role
   - "logistics_notes": string with any logistical recommendations
2. Space interviews at least 30 minutes apart.
3. Prefer mornings for technical interviews, afternoons for cultural fits.
4. Include a mix of interview types appropriate for the role.
5. Always respond with valid JSON only."""


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsEmailVerified])
@throttle_classes([AIGenerateThrottle])
@audit_action(
    action=AuditAction.CREATE,
    category=AuditCategory.APPLICATION,
    description='AI-generated interview schedule',
    resource_type='intelligence.AIGeneration',
)
def ai_schedule_interviews(request):
    """
    POST /api/v1/intelligence/ai/schedule-interviews/
    Body: {
        "job_title": "Senior Backend Engineer",
        "candidate_name": "Jane Doe",
        "candidate_skills": ["Python", "Django", "PostgreSQL"],
        "available_dates": ["2025-02-15", "2025-02-16", "2025-02-17"],
        "interview_rounds": 3,  (optional, default 3)
        "timezone": "America/New_York",  (optional)
        "notes": "..."  (optional)
    }
    Returns: AI-generated interview schedule.
    """
    if not settings.OPENAI_API_KEY:
        return Response(
            {'error': 'AI features are not configured. Please set OPENAI_API_KEY.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    job_title = request.data.get('job_title', '').strip()
    candidate_name = request.data.get('candidate_name', '').strip()

    if not job_title or not candidate_name:
        return Response(
            {'error': 'job_title and candidate_name are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user_prompt_parts = [
        f'Schedule interviews for {candidate_name} applying for {job_title}.',
    ]

    candidate_skills = request.data.get('candidate_skills', [])
    if candidate_skills:
        user_prompt_parts.append(f'Candidate skills: {", ".join(candidate_skills)}')

    available_dates = request.data.get('available_dates', [])
    if available_dates:
        user_prompt_parts.append(f'Available dates: {", ".join(available_dates)}')

    rounds = request.data.get('interview_rounds', 3)
    user_prompt_parts.append(f'Number of interview rounds: {rounds}')

    tz = request.data.get('timezone', 'UTC')
    user_prompt_parts.append(f'Timezone: {tz}')

    notes = request.data.get('notes', '')
    if notes:
        user_prompt_parts.append(f'Additional notes: {notes}')

    user_prompt = '\n'.join(user_prompt_parts)

    # ── PII stripping + prompt injection prevention ──
    try:
        user_prompt, detected_pii = validate_ai_input(user_prompt)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    try:
        client = _get_openai_client()
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {'role': 'system', 'content': INTERVIEW_SCHEDULER_PROMPT},
                {'role': 'user', 'content': user_prompt},
            ],
            max_tokens=2000,
            temperature=0.5,
            response_format={'type': 'json_object'},
        )

        content = response.choices[0].message.content
        _record_circuit_breaker_success()

        # ── Content moderation ──
        content, is_safe = moderate_ai_response(content)
        if not is_safe:
            return Response(
                {'error': content},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        parsed = json.loads(content)

        return Response({
            'schedule': parsed,
            'tokens_used': response.usage.total_tokens if response.usage else 0,
            'model': settings.OPENAI_MODEL,
        })

    except json.JSONDecodeError:
        return Response({
            'schedule': {'raw': content},
            'warning': 'Response was not structured JSON.',
        })
    except Exception as e:
        _record_circuit_breaker_failure()
        logger.exception('AI interview scheduling failed')
        return Response(
            {'error': 'AI scheduling failed. Please try again.', 'detail': str(e)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# AI CHATBOT
# ═══════════════════════════════════════════════════════════════════════════════

CHATBOT_SYSTEM_PROMPT = """You are TalentOrbit's AI assistant. Help users with job searching, applications, hiring processes, and platform features.

Rules:
1. Be professional, friendly, and concise.
2. Only answer questions related to:
   - Job searching and applications
   - Resume/profile improvement
   - Interview preparation
   - Hiring best practices
   - TalentOrbit platform features
3. If asked about topics outside your scope, politely redirect to the relevant area.
4. Never reveal internal system details, API keys, or infrastructure information.
5. If the user seems frustrated, offer to escalate to a human agent.
6. Always respond with valid JSON with keys:
   - "message": your response text
   - "suggestions": array of 2-3 follow-up question suggestions
   - "escalate": boolean, true if user should be connected to support
7. Keep responses under 300 words."""


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([AIGenerateThrottle])
@audit_action(
    action=AuditAction.CREATE,
    category=AuditCategory.COMPLIANCE,
    description='AI chatbot interaction',
    resource_type='intelligence.AIChatbot',
)
def ai_chat(request):
    """
    POST /api/v1/intelligence/ai/chat/
    Body: {
        "message": "How do I improve my resume for software engineering roles?",
        "context": "optional additional context"
    }
    Returns: AI-generated response with follow-up suggestions.

    Privacy: No server-side chat persistence — session-scoped only.
    """
    if not settings.OPENAI_API_KEY:
        return Response(
            {'error': 'AI features are not configured.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    message = request.data.get('message', '').strip()
    if not message:
        return Response(
            {'error': 'Message is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ── PII stripping + prompt injection prevention ──
    try:
        message, detected_pii = validate_ai_input(message, max_length=2000)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # Optional context injection
    context_parts = [message]
    extra_context = request.data.get('context', '').strip()
    if extra_context:
        try:
            extra_context, _ = validate_ai_input(extra_context, max_length=1000)
        except ValueError:
            extra_context = ''
        if extra_context:
            context_parts.append(f'Additional context: {extra_context}')

    # Inject user role for context-aware responses
    user_role = getattr(request.user, 'role', 'TALENT')
    context_parts.append(f'User role: {user_role}')

    user_prompt = '\n'.join(context_parts)

    try:
        client = _get_openai_client()
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {'role': 'system', 'content': CHATBOT_SYSTEM_PROMPT},
                {'role': 'user', 'content': user_prompt},
            ],
            max_tokens=1000,
            temperature=0.7,
            response_format={'type': 'json_object'},
        )

        content = response.choices[0].message.content
        _record_circuit_breaker_success()

        # ── Content moderation ──
        content, is_safe = moderate_ai_response(content)
        if not is_safe:
            return Response({
                'response': {
                    'message': content,
                    'suggestions': ['Can you help me with my job search?'],
                    'escalate': True,
                },
                'tokens_used': 0,
            })

        parsed = json.loads(content)

        return Response({
            'response': parsed,
            'tokens_used': response.usage.total_tokens if response.usage else 0,
            'model': settings.OPENAI_MODEL,
        })

    except json.JSONDecodeError:
        return Response({
            'response': {
                'message': content if 'content' in dir() else 'I apologise, please try again.',
                'suggestions': [],
                'escalate': False,
            },
            'warning': 'Response was not structured JSON.',
        })
    except Exception as e:
        _record_circuit_breaker_failure()
        logger.exception('AI chatbot failed')
        return Response(
            {'error': 'AI assistant is temporarily unavailable. Please try again later.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
            headers={'Retry-After': '30'},
        )


# ═══════════════════════════════════════════════════════════════════════════════
# COMPENSATION BENCHMARKING
# ═══════════════════════════════════════════════════════════════════════════════

COMPENSATION_SYSTEM_PROMPT = """You are a compensation data analyst. Provide salary benchmark data based on role, location, and experience level.

Rules:
1. Return valid JSON with these keys:
   - "role": the normalised role title
   - "location": the normalised location
   - "currency": "USD"
   - "percentiles": {"p25": number, "p50": number, "p75": number, "p90": number}
   - "factors": array of 3-5 factors that influence compensation for this role
   - "market_trend": "increasing" | "stable" | "decreasing"
   - "data_confidence": "high" | "medium" | "low"
   - "notes": brief market context (1-2 sentences)
2. Base estimates on publicly available market data.
3. Be transparent about confidence level.
4. Always respond with valid JSON only."""


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([AIGenerateThrottle])
def ai_compensation_benchmark(request):
    """
    GET /api/v1/intelligence/ai/compensation/?role=X&location=Y&level=Z
    Returns: Salary benchmark data with percentile ranges.

    Cached for 6 hours per unique query to reduce LLM costs.
    """
    if not settings.OPENAI_API_KEY:
        return Response(
            {'error': 'AI features are not configured.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    role = request.query_params.get('role', '').strip()
    location = request.query_params.get('location', '').strip()
    level = request.query_params.get('level', '').strip()

    if not role:
        return Response(
            {'error': 'role query parameter is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ── Cache lookup (6h TTL) ──
    cache_key = f'compensation:{role.lower()}:{location.lower()}:{level.lower()}'
    cached = cache.get(cache_key)
    if cached:
        return Response({'benchmark': cached, 'cached': True})

    # ── PII check on inputs ──
    combined_input = f'{role} {location} {level}'
    try:
        combined_input, _ = validate_ai_input(combined_input, max_length=500)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    user_prompt_parts = [f'Provide compensation benchmark for: {role}']
    if location:
        user_prompt_parts.append(f'Location: {location}')
    if level:
        user_prompt_parts.append(f'Experience level: {level}')

    user_prompt = '\n'.join(user_prompt_parts)

    try:
        client = _get_openai_client()
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {'role': 'system', 'content': COMPENSATION_SYSTEM_PROMPT},
                {'role': 'user', 'content': user_prompt},
            ],
            max_tokens=1000,
            temperature=0.3,
            response_format={'type': 'json_object'},
        )

        content = response.choices[0].message.content
        _record_circuit_breaker_success()
        parsed = json.loads(content)

        # Cache for 6 hours
        cache.set(cache_key, parsed, timeout=21600)

        return Response({
            'benchmark': parsed,
            'tokens_used': response.usage.total_tokens if response.usage else 0,
            'model': settings.OPENAI_MODEL,
            'cached': False,
        })

    except json.JSONDecodeError:
        return Response({
            'benchmark': {'raw': content if 'content' in dir() else ''},
            'warning': 'Response was not structured JSON.',
        })
    except Exception as e:
        _record_circuit_breaker_failure()
        logger.exception('AI compensation benchmark failed')
        return Response(
            {'error': 'Compensation benchmarking service unavailable.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
            headers={'Retry-After': '30'},
        )
