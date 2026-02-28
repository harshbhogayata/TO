from rest_framework import serializers
from .models import Course

class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ['id', 'category', 'module_name', 'title', 'duration', 'img_url', 'url', 'is_coming_soon', 'created_at']
        read_only_fields = ['id', 'created_at']
