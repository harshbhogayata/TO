"""
talentorbit/exceptions.py
Custom DRF exception handler — ensures ALL API errors are JSON, never HTML.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        return response

    # Catch any unhandled exception and return JSON 500
    return Response(
        {'detail': 'Internal server error.'},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
