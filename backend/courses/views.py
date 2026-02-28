from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import Course
from .serializers import CourseSerializer

class CourseListView(generics.ListAPIView):
    """GET /api/v1/courses/ — Paginated resource list of courses"""
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]
    queryset = Course.objects.all()
