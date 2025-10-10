from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ApplicationViewSet, DocumentListCreateView, ChangeApplicationStageView

# 🔹 Routerni prefixsiz e’lon qilamiz
router = DefaultRouter()
router.register("", ApplicationViewSet, basename="application")

urlpatterns = [
    # 📋 CRUD (GET, POST, PUT, DELETE)
    path("", include(router.urls)),

    # 📎 Hujjatlar (arizaga fayl biriktirish)
    path(
        "<int:application_id>/documents/",
        DocumentListCreateView.as_view(),
        name="application-documents",
    ),

    # 🔁 Bosqichni o‘zgartirish (faqat operator/admin)
    path(
        "<int:application_id>/change-stage/",
        ChangeApplicationStageView.as_view(),
        name="application-change-stage",
    ),
]
