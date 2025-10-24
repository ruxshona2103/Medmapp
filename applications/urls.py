# applications/urls.py
# ===============================================================
# APPLICATIONS URLS - PATH PARAM TO'G'RI KONFIGURATSIYA
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
)

# ===============================================================
# ROUTER
# ===============================================================
router = DefaultRouter()
router.register(r'applications', ApplicationViewSet, basename='application')
router.register(r'completed-applications', CompletedApplicationViewSet, basename='completed-application')

# ===============================================================
# URL PATTERNS
# ===============================================================
urlpatterns = [
    # Router URLs
    path('', include(router.urls)),

    # ============================================================
    # 👤 PATIENT APPLICATIONS - PATH PARAM
    # ============================================================
    # ✅ TO'G'RI URL pattern:
    # GET /api/applications/patient/19/        → List
    # GET /api/applications/patient/19/39/     → Retrieve

    path('applications/patient/<int:patient_id>/',
         PatientApplicationViewSet.as_view({'get': 'list'}),
         name='patient-applications-list'),

    path('applications/patient/<int:patient_id>/<int:pk>/',
         PatientApplicationViewSet.as_view({'get': 'retrieve'}),
         name='patient-applications-detail'),

    # ============================================================
    # 📎 DOCUMENTS
    # ============================================================
    path('applications/<int:application_id>/documents/',
         DocumentListCreateView.as_view(),
         name='application-documents'),

    # ============================================================
    # 🏷️ STAGE VA STATUS
    # ============================================================
    path('applications/<int:application_id>/change-stage/',
         ChangeApplicationStageView.as_view(),
         name='change-application-stage'),

    path('applications/<int:application_id>/change-status/',
         ChangeApplicationStatusView.as_view(),
         name='change-application-status'),
]
