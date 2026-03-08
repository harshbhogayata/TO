"""
Dedicated throttle classes for resume parsing endpoints.
"""
from rest_framework.throttling import ScopedRateThrottle


class AuthenticatedResumeParseThrottle(ScopedRateThrottle):
    scope = 'resume_authenticated'


class PublicResumeParseThrottle(ScopedRateThrottle):
    scope = 'resume_public'


class AuthenticatedAIResumeParseThrottle(ScopedRateThrottle):
    scope = 'ai_resume_authenticated'


class PublicAIResumeParseThrottle(ScopedRateThrottle):
    scope = 'ai_resume_public'
