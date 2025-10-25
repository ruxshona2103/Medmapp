# applications/urls.py
# ===============================================================
# APPLICATIONS URLS - TO'G'RI TARTIB (MUHIM!)
# ===============================================================

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ApplicationViewSet,
    PatientApplicationViewSet,
    CompletedApplicationViewSet,
    DocumentListCreateView,
    ChangeApplicationStageView,
    ChangeApplicationStatusView,
    application_statistics,
)

# ===============================================================
# ROUTER
# ===============================================================
router = DefaultRouter()
router.register(r'applications', ApplicationViewSet, basename='application')
router.register(r'completed-applications', CompletedApplicationViewSet, basename='completed-applications')

# ===============================================================
# URL PATTERNS - MUHIM: TARTIB TO'G'RI BO'LISHI KERAK!
# ===============================================================
urlpatterns = [
    # ✅ 1. AVVAL - Maxsus pathlar (router'dan oldin)

    # Statistics - ✅ ROUTER'DAN OLDIN!
    path('applications/statistics/',
         application_statistics,
         name='application-statistics'),

    # Patient applications - LIST
    path('applications/patient/<int:patient_id>/',
         PatientApplicationViewSet.as_view({'get': 'list'}),
         name='patient-applications-list'),

    # Patient applications - RETRIEVE
    path('applications/patient/<int:patient_id>/<int:pk>/',
         PatientApplicationViewSet.as_view({'get': 'retrieve'}),
         name='patient-applications-detail'),

    # Documents
    path('applications/<int:application_id>/documents/',
         DocumentListCreateView.as_view(),
         name='application-documents'),

    # Stage change
    path('applications/<int:application_id>/change-stage/',
         ChangeApplicationStageView.as_view(),
         name='change-application-stage'),

    # Status change
    path('applications/<int:application_id>/change-status/',
         ChangeApplicationStatusView.as_view(),
         name='change-application-status'),

    # ✅ 2. KEYIN - Router (oxirida)
    path('', include(router.urls)),
]
