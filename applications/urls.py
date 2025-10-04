from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ApplicationViewSet,
    DocumentListCreateView,
    ChangeApplicationStageView,
)

router = DefaultRouter()
router.register(r'applications', ApplicationViewSet, basename='application')

urlpatterns = [
    path('', include(router.urls)),
    path('applications/<int:application_id>/documents/', DocumentListCreateView.as_view(), name='application-documents'),
    path('applications/<int:application_id>/change-stage/', ChangeApplicationStageView.as_view(), name='application-change-stage'),
]