from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ApplicationCreateView,
    ApplicationStatusView,
    ApplicationViewSet,
    ChangeApplicationStageView,
    DocumentCreateView,
    DocumentListCreateView,
    DocumentListView
)

router = DefaultRouter()
router.register(r'applications', ApplicationViewSet, basename="applications")

urlpatterns = [
    path("application/create/", ApplicationCreateView.as_view(), name="application-create"),
    path("application/status/", ApplicationStatusView.as_view(), name="application-status"),
    path('applications/<int:application_id>/documents/', DocumentListCreateView.as_view(), name='application-documents'),
    path('applications/<int:application_id>/change-stage/', ChangeApplicationStageView.as_view(), name='application-change-stage'),
    path("applications/<str:application_id>/documents/", DocumentCreateView.as_view(), name="document-create"),
    path("documents/", DocumentListView.as_view(), name="document-list"),
    path("", include(router.urls)),
]
