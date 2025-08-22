from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ApplicationCreateView,
    ApplicationStatusView,
    ApplicationViewSet
)

router = DefaultRouter()
router.register(r'applications', ApplicationViewSet, basename="applications")

urlpatterns = [
    path("application/create/", ApplicationCreateView.as_view(), name="application-create"),
    path("application/status/", ApplicationStatusView.as_view(), name="application-status"),
    path("", include(router.urls)),  # -> /applications/ ishlaydi
]
