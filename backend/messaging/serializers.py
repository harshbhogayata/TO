"""
messaging/serializers.py
"""
from rest_framework import serializers
from .models import Thread, Message


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.ReadOnlyField(source='sender.full_name')
    sender_role = serializers.ReadOnlyField(source='sender.role')

    class Meta:
        model = Message
        fields = ('id', 'thread', 'sender', 'sender_name', 'sender_role',
                  'body', 'attachment', 'read', 'read_at', 'sent_at')
        read_only_fields = ('id', 'sender', 'read', 'read_at', 'sent_at')


# Allowed attachment types and size limit for messages
_MSG_ATTACHMENT_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_MSG_ATTACHMENT_ALLOWED_TYPES = {
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain',
}


class SendMessageSerializer(serializers.ModelSerializer):
    body = serializers.CharField(max_length=10000)

    class Meta:
        model = Message
        fields = ('thread', 'body', 'attachment')

    def validate_attachment(self, value):
        if value is None:
            return value
        if value.size > _MSG_ATTACHMENT_MAX_BYTES:
            raise serializers.ValidationError(
                f'Attachment too large. Maximum size is {_MSG_ATTACHMENT_MAX_BYTES // (1024*1024)} MB.'
            )
        content_type = getattr(value, 'content_type', '').split(';')[0].strip().lower()
        if content_type and content_type not in _MSG_ATTACHMENT_ALLOWED_TYPES:
            raise serializers.ValidationError(
                'Unsupported file type. Allowed: images, PDF, Word, plain text.'
            )
        return value

    def create(self, validated_data):
        validated_data['sender'] = self.context['request'].user
        msg = super().create(validated_data)
        # Touch thread.updated_at for ordering
        msg.thread.save(update_fields=['updated_at'])
        return msg


class ThreadSerializer(serializers.ModelSerializer):
    participants = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    job_title = serializers.SerializerMethodField()

    class Meta:
        model = Thread
        fields = ('id', 'participants', 'job', 'job_title',
                  'last_message', 'unread_count', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

    def get_participants(self, obj):
        return [
            {'id': p.id, 'full_name': p.full_name, 'email': p.email, 'role': p.role}
            for p in obj.participants.all()
        ]

    def get_last_message(self, obj):
        msg = obj.messages.order_by('-sent_at').first()
        if msg:
            return {
                'body': msg.body,
                'sender_name': msg.sender.full_name,
                'sent_at': msg.sent_at,
            }
        return None

    def get_unread_count(self, obj):
        user = self.context['request'].user
        return obj.messages.filter(read=False).exclude(sender=user).count()

    def get_job_title(self, obj):
        return obj.job.title if obj.job else None


class CreateThreadSerializer(serializers.Serializer):
    """Start a new thread with another user (by email or ID)."""
    recipient_id = serializers.IntegerField(required=False, allow_null=True)
    recipient_email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    job_id = serializers.IntegerField(required=False, allow_null=True)
    initial_message = serializers.CharField(required=False, allow_blank=True, max_length=10000)
