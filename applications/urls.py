from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ApplicationViewSet,
    DocumentListCreateView,
    ChangeApplicationStageView,
    CompletedApplicationViewSet,
)
from .views_operator import ChangeApplicationStatusView

# 🔹 Router — avtomatik CRUD endpointlar uchun
router = DefaultRouter()
router.register(r"applications", ApplicationViewSet, basename="applications")
router.register(r"completed-applications", CompletedApplicationViewSet, basename="completed-applications")

urlpatterns = [
    path("", include(router.urls)),

    # 🔹 Hujjatlar uchun
    path(
        "applications/<int:application_id>/documents/",
        DocumentListCreateView.as_view(),
        name="application-documents",
    ),

    # 🔹 Bosqichni o‘zgartirish uchun
    path(
        "applications/<int:application_id>/change-stage/",
        ChangeApplicationStageView.as_view(),
        name="application-change-stage",
    ),
    path(
    "applications/<int:application_id>/change-status/",
    ChangeApplicationStatusView.as_view(),
    name="application-change-status",
    ),

]
