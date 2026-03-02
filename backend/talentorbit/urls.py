"""
talentorbit/urls.py
Root URL configuration.
All API endpoints are versioned under /api/v1/.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse


# ─── Health check (for uptime monitors / load balancers) ──────────────────────
def health_check(request):
    return JsonResponse({'status': 'ok'})


# ─── JSON 404/500 handlers for API routes ─────────────────────────────────────
def handler404_view(request, exception=None):
    return JsonResponse({'detail': 'Not found.'}, status=404)


def handler500_view(request):
    return JsonResponse({'detail': 'Internal server error.'}, status=500)


handler404 = handler404_view
handler500 = handler500_view

urlpatterns = [
    # Health check
    path('health/', health_check, name='health_check'),

    # Admin panel
    path('admin/', admin.site.urls),

    # API v1
    path('api/v1/auth/', include('accounts.urls')),
    path('api/v1/jobs/', include('jobs.urls')),
    path('api/v1/messages/', include('messaging.urls')),
    path('api/v1/admin-api/', include('admin_api.urls')),
    path('api/v1/payments/', include('payments.urls')),
    path('api/v1/blog/', include('blog.urls')),
    path('api/v1/notifications/', include('notifications.urls')),
    path('api/v1/courses/', include('courses.urls')),
]

# Serve uploaded media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
