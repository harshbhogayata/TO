from rest_framework import generics, views, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Notification
from .serializers import NotificationSerializer

class NotificationListView(generics.ListAPIView):
    """GET /api/v1/notifications/ — List user notifications"""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        return self.request.user.notifications.all()

class NotificationReadView(views.APIView):
    """PATCH /api/v1/notifications/<id>/read/ — Mark single as read"""
    permission_classes = [IsAuthenticated]
    def patch(self, request, pk):
        try:
            notif = request.user.notifications.get(pk=pk)
            notif.is_read = True
            notif.save(update_fields=['is_read'])
            return Response({'status': 'read'})
        except Notification.DoesNotExist:
            return Response(status=404)

class NotificationReadAllView(views.APIView):
    """POST /api/v1/notifications/read-all/ — Mark all as read"""
    permission_classes = [IsAuthenticated]
    def post(self, request):
        request.user.notifications.filter(is_read=False).update(is_read=True)
        return Response({'status': 'all_read'})
