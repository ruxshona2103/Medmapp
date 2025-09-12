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
    permission_classes=[permissions.AllowAny],   # <<< MUHIM
)

urlpatterns = [
    path("", lambda request: redirect("schema-swagger-ui")),

    path("admin/", admin.site.urls),

    # app urls
    path("api/auth/", include("authentication.urls")),
    path("api/patients/", include("patients.urls")),
    path("api/services/", include("services.urls")),
    path("api/applications/", include("applications.urls")),
    path("api/consultations/", include("consultations.urls")),
    path("api/reviews/", include("reviews.urls")),

    # swagger/redoc
    re_path(r"^swagger(?P<format>\.json|\.yaml)$", schema_view.without_ui(cache_timeout=0), name="schema-json"),
    path("swagger/", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),

]
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
