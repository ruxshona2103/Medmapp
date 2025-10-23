from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ApplicationViewSet,
    PatientApplicationViewSet,
    CompletedApplicationViewSet,
    DocumentListCreateView,
    ChangeApplicationStageView,
    ChangeApplicationStatusView,
)

router = DefaultRouter()
router.register(r'applications', ApplicationViewSet, basename='application')
router.register(r'completed-applications', CompletedApplicationViewSet, basename='completed-application')

urlpatterns = [
    path('', include(router.urls)),

    # 👤 Patient ID bo'yicha arizalar
    path('applications/patient/<int:patient_id>/',
         PatientApplicationViewSet.as_view({'get': 'list'}),
         name='patient-applications-list'),

    path('applications/patient/<int:patient_id>/<int:pk>/',
         PatientApplicationViewSet.as_view({'get': 'retrieve'}),
         name='patient-applications-detail'),
    path('applications/<int:application_id>/documents/',
         DocumentListCreateView.as_view(),
         name='application-documents'),
    path('applications/<int:application_id>/change-stage/',
         ChangeApplicationStageView.as_view(),
         name='change-application-stage'),
    path('applications/<int:application_id>/change-status/',
         ChangeApplicationStatusView.as_view(),
         name='change-application-status'),
]