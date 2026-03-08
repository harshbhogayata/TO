"""
AI-enhanced resume parsing views with feature flags for gradual rollout.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsEmailVerified

from .models import ParsedResume
from .permissions import IsTalent
from .serializers import ResumeUploadSerializer, normalise_resume_payload
from .throttling import (
    AuthenticatedAIResumeParseThrottle,
    PublicAIResumeParseThrottle,
)

logger = logging.getLogger(__name__)


class _BaseResumeAIEnhancedView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    feature_flag_name = 'USE_AI_ENHANCED_RESUME_PARSING'
    success_status = status.HTTP_200_OK

    def get_request_user(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            return user
        return None

    def _build_response(self, parsed, user, *, feature_flag_used=None):
        if user:
            instance = ParsedResume.objects.filter(user=user).first()
            if instance:
                payload = normalise_resume_payload(
                    instance,
                    cached=parsed.get('cached', False),
                    feature_flag_used=feature_flag_used,
                )
            else:
                payload = normalise_resume_payload(
                    parsed,
                    feature_flag_used=feature_flag_used,
                )
        else:
            payload = normalise_resume_payload(
                parsed,
                cached=False,
                feature_flag_used=feature_flag_used,
            )
        return Response(payload, status=self.success_status)

    def _parse_with_fallback(self, resume_file, user):
        from .nlp.parser import parse_resume

        logger.info(
            'AI-enhanced parsing disabled; using traditional parser for %s request',
            'authenticated' if user else 'public',
        )
        return parse_resume(resume_file, user=user), None

    def _parse_with_ai(self, resume_file, user):
        from .nlp.ai_enhanced_parser import parse_resume_ai_enhanced

        parsed = parse_resume_ai_enhanced(resume_file, user=user)
        feature_flag_used = None
        parser_version = str(parsed.get('parser_version', ''))
        if parser_version.startswith('ai_enhanced'):
            feature_flag_used = self.feature_flag_name
        return parsed, feature_flag_used

    def post(self, request):
        upload_serializer = ResumeUploadSerializer(data=request.data)
        upload_serializer.is_valid(raise_exception=True)

        resume_file = upload_serializer.validated_data['resume']
        user = self.get_request_user(request)

        try:
            if getattr(settings, self.feature_flag_name, False):
                parsed, feature_flag_used = self._parse_with_ai(resume_file, user)
            else:
                parsed, feature_flag_used = self._parse_with_fallback(resume_file, user)
        except Exception:
            logger.exception(
                'AI-enhanced resume parsing failed for %s',
                f'user {user.id}' if user else 'public request',
            )
            return Response(
                {'detail': 'Resume parsing failed. Please try a different file.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return self._build_response(
            parsed,
            user,
            feature_flag_used=feature_flag_used,
        )


class ParseResumeAIEnhancedView(_BaseResumeAIEnhancedView):
    """
    POST /api/v1/intelligence/parse-resume-ai/

    AI-enhanced resume parsing for authenticated talent users.
    """

    permission_classes = [permissions.IsAuthenticated, IsTalent, IsEmailVerified]
    throttle_classes = [AuthenticatedAIResumeParseThrottle]
    success_status = status.HTTP_201_CREATED


class ParseResumeAIEnhancedPublicView(_BaseResumeAIEnhancedView):
    """
    POST /api/v1/intelligence/parse-resume-ai-public/

    Unauthenticated AI-enhanced resume parsing for registration.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [PublicAIResumeParseThrottle]
    success_status = status.HTTP_200_OK


def get_ai_parsing_stats():
    """Get statistics about AI-enhanced parsing usage."""
    if not getattr(settings, 'USE_AI_ENHANCED_RESUME_PARSING', False):
        return {'enabled': False, 'message': 'AI-enhanced parsing is disabled'}

    yesterday = timezone.now() - timedelta(days=1)
    ai_queryset = ParsedResume.objects.filter(
        parser_version__startswith='ai_enhanced',
        parsed_at__gte=yesterday,
    )
    total_queryset = ParsedResume.objects.filter(parsed_at__gte=yesterday)

    ai_count = ai_queryset.count()
    total_count = total_queryset.count()

    return {
        'enabled': True,
        'feature_flag': 'USE_AI_ENHANCED_RESUME_PARSING',
        'ai_enhanced_parses_24h': ai_count,
        'total_parses_24h': total_count,
        'ai_enhancement_rate': round(ai_count / max(total_count, 1) * 100, 2),
    }
