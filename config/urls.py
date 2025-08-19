# project/urls.py

from django.contrib import admin
from django.urls import path, include
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

# Swagger schema view
schema_view = get_schema_view(
    openapi.Info(
        title="MedMap API",
        default_version='v1',
        description="Tibbiy yo‘nalishlar API hujjati",
        contact=openapi.Contact(email="support@medmap.uz"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('patients.urls')),
    path('api/', include('authentication.urls')),


    # Swagger UI
    path('', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
]
