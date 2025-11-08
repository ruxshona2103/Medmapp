# config/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.shortcuts import redirect
from rest_framework import permissions
from django.conf import settings
from django.conf.urls.static import static

schema_view = get_schema_view(
    openapi.Info(
        title="MedMapp API",
        default_version="v1",
        description="MedMapp loyihasi uchun API hujjatlar",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="support@medmapp.uz"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    path("", lambda request: redirect("schema-swagger-ui")),

    path("admin/", admin.site.urls),

    # app urls
    path("api/", include("authentication.urls")),
    path("api/", include("services.urls")),
    path("api/", include("applications.urls")),
    path("api/", include("core.urls")),
    path("api/", include("consultations.urls")),
    path("api/", include("clinics.urls")),
    path("api/", include("patients.urls")),
    path("api/", include("partners.urls")),
    path("api/", include("review.urls")),

    # swagger/redoc
    re_path(r"^swagger(?P<format>\.json|\.yaml)$", schema_view.without_ui(cache_timeout=0), name="schema-json"),
    path("swagger/", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
]

# ===============================================================
# MEDIA VA STATIC FILES
# ===============================================================
# Development uchun media files serve qilish
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Development uchun static files serve qilish
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)