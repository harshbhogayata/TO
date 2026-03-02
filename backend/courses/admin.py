from django.contrib import admin
from .models import Course


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'module_name', 'duration', 'is_coming_soon', 'created_at')
    list_filter = ('category', 'is_coming_soon')
    search_fields = ('title', 'module_name')
    readonly_fields = ('created_at',)
