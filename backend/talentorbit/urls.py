"""
talentorbit/urls.py
Root URL configuration.
All API endpoints are versioned under /api/v1/.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
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
