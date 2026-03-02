"""
messaging/views.py
"""
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsEmailVerified
from .models import Thread, Message
from .serializers import (
    ThreadSerializer, MessageSerializer,
    SendMessageSerializer, CreateThreadSerializer
)


class MyThreadsView(generics.ListAPIView):
    """GET /api/messages/ — List all threads for the authenticated user."""
    serializer_class = ThreadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Thread.objects.filter(
            participants=self.request.user
        ).prefetch_related('participants', 'messages__sender').select_related('job')


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def create_thread(request):
    """
    POST /api/messages/thread/
    Start a new conversation with another platform user.
    If a thread already exists between these two users (optionally for the same job),
    return the existing thread instead of creating a duplicate.
    """
    # Email verification check for thread creation
    if not request.user.is_verified:
        return Response(
            {'detail': 'Please verify your email address before sending messages.'},
            status=403
        )

    s = CreateThreadSerializer(data=request.data)
    s.is_valid(raise_exception=True)

    recipient_id = s.validated_data.get('recipient_id')
    recipient_email = s.validated_data.get('recipient_email')
    
    if not recipient_id and not recipient_email:
        return Response({'detail': 'Must provide recipient_id or recipient_email.'}, status=400)

    job_id = s.validated_data.get('job_id')
    initial_message = s.validated_data.get('initial_message', '')

    if recipient_id:
        recipient = get_object_or_404(User, pk=recipient_id)
    else:
        recipient = get_object_or_404(User, email__iexact=recipient_email)

    if request.user == recipient:
        return Response({'detail': 'You cannot start a thread with yourself.'}, status=400)

    # Atomic block to prevent duplicate thread creation race condition
    with transaction.atomic():
        existing = Thread.objects.filter(
            participants=request.user
        ).filter(
            participants=recipient
        )
        if job_id:
            existing = existing.filter(job_id=job_id)

        if existing.exists():
            thread = existing.first()
            created = False
        else:
            thread = Thread.objects.create(job_id=job_id)
            thread.participants.add(request.user, recipient)
            created = True

    if initial_message:
        Message.objects.create(thread=thread, sender=request.user, body=initial_message)
        thread.save(update_fields=['updated_at'])

    return Response(
        ThreadSerializer(thread, context={'request': request}).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )


class ThreadMessagesView(generics.ListAPIView):
    """GET /api/messages/<thread_id>/messages/ — Fetch all messages in a thread."""
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        thread_id = self.kwargs['thread_id']
        # Ensure the user is a participant
        thread = get_object_or_404(
            Thread, pk=thread_id, participants=self.request.user
        )
        # Mark all messages from others as read with timestamp
        now = timezone.now()
        updated = thread.messages.exclude(
            sender=self.request.user
        ).filter(read=False).update(read=True, read_at=now)

        # Broadcast read receipt via WebSocket if any messages were marked
        if updated > 0:
            from realtime.broadcast import broadcast_thread_message
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            layer = get_channel_layer()
            if layer:
                try:
                    async_to_sync(layer.group_send)(
                        f'thread_{thread_id}',
                        {
                            'type': 'chat_read',
                            'thread_id': thread_id,
                            'user_id': self.request.user.id,
                            'user_name': self.request.user.full_name or self.request.user.email,
                        },
                    )
                except Exception:
                    pass  # Non-critical: WS broadcast failure shouldn't break REST

        return thread.messages.select_related('sender').all()


class SendMessageView(generics.CreateAPIView):
    """POST /api/messages/send/ — Send a message in an existing thread."""
    serializer_class = SendMessageSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmailVerified]

    def perform_create(self, serializer):
        thread = serializer.validated_data['thread']
        # Security: only participants can send
        if self.request.user not in thread.participants.all():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You are not a participant of this thread.')
        serializer.save()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        # Return full message data (with id, sender, sender_name, sent_at, etc.)
        response_serializer = MessageSerializer(
            serializer.instance, context={'request': request}
        )
        headers = self.get_success_headers(response_serializer.data)

        # ── Broadcast to WebSocket (for users connected via WS) ──────────
        msg = serializer.instance
        from realtime.broadcast import broadcast_thread_message
        broadcast_thread_message(msg.thread_id, {
            'id': msg.id,
            'thread_id': msg.thread_id,
            'sender': msg.sender_id,
            'sender_name': msg.sender.full_name or msg.sender.email,
            'sender_role': msg.sender.role,
            'body': msg.body,
            'read': False,
            'sent_at': msg.sent_at.isoformat(),
        })

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def unread_count(request):
    """GET /api/messages/unread/ — Total unread message count for the user."""
    total_unread = Message.objects.filter(
        thread__participants=request.user,
        read=False
    ).exclude(
        sender=request.user
    ).count()
    return Response({'unread': total_unread})
