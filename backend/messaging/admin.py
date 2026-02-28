"""
messaging/admin.py
"""
from django.contrib import admin
from .models import Thread, Message


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ['id', 'participant_list', 'job', 'created_at', 'updated_at']
    filter_horizontal = ['participants']

    def participant_list(self, obj):
        return ', '.join(p.full_name or p.email for p in obj.participants.all())

    participant_list.short_description = 'Participants'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'thread', 'body_preview', 'read', 'sent_at']
    list_filter = ['read']
    search_fields = ['sender__email', 'body']

    def body_preview(self, obj):
        return obj.body[:60]

    body_preview.short_description = 'Preview'
