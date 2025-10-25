# patients/urls.py
# ===============================================================
# PATIENTS URLS - TO'G'RI TARTIB
# ===============================================================

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PatientViewSet,
    PatientDocumentViewSet,
    ResponseLettersViewSet,
    ContractApproveViewSet,
    MeProfileView,
    patient_statistics,
)

# ===============================================================
# ROUTER
# ===============================================================
router = DefaultRouter()
router.register(r"patients", PatientViewSet, basename="patient")
router.register(r"response-letters", ResponseLettersViewSet, basename="response-letters")
router.register(r"contracts", ContractApproveViewSet, basename="contracts")

# ===============================================================
# URL PATTERNS - TO'G'RI TARTIB!
# ===============================================================
urlpatterns = [
    # ✅ 1. AVVAL - Maxsus pathlar (router'dan oldin)

    # Statistics - ✅ ROUTER'DAN OLDIN!
    path("patients/statistics/",
         patient_statistics,
         name="patient-statistics"),

    # Patient documents
    path("patients/<int:patient_pk>/documents/",
         PatientDocumentViewSet.as_view({"post": "create"}),
         name="patient-docs-create"),

    path("documents/<int:pk>/",
         PatientDocumentViewSet.as_view({"delete": "destroy"}),
         name="patient-docs-delete"),

    # Profile
    path("me/profile/",
         MeProfileView.as_view(),
         name="me-profile"),

    # ✅ 2. KEYIN - Router (oxirida)
    path('', include(router.urls)),
]
