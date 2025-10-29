# patients/urls.py
# ===============================================================
# PATIENTS URLS - TO'G'RI TARTIB (documents va responses bir joyda)
# ===============================================================

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    PatientViewSet,
    PatientDocumentViewSet,
    ContractApproveViewSet,
    MeProfileView,
    patient_statistics,
    PatientResponseListView,
)

# ===============================================================
# ROUTER
# ===============================================================
router = DefaultRouter()
router.register(r"patients", PatientViewSet, basename="patient")
router.register(r"contracts", ContractApproveViewSet, basename="contracts")

# ===============================================================
# URL PATTERNS - TO'G'RI TARTIB!
# ===============================================================
urlpatterns = [
    # ✅ 1. AVVAL - Maxsus pathlar (router'dan oldin)

    # 📊 Statistics
    path(
        "patients/statistics/",
        patient_statistics,
        name="patient-statistics"
    ),

    # ============================================================
    # 📎 DOCUMENTS (bemor fayllari va response fayllar bir joyda)
    # ============================================================

    # Bemor uchun yangi hujjat yuklash
    path(
        "patients/<int:patient_pk>/documents/",
        PatientDocumentViewSet.as_view({"post": "create"}),
        name="patient-docs-create"
    ),

    # Hujjatni o‘chirish
    path(
        "documents/<int:pk>/",
        PatientDocumentViewSet.as_view({"delete": "destroy"}),
        name="patient-docs-delete"
    ),

    # 👩‍⚕️ Bemor → o‘ziga yuborilgan fayllarni ko‘radi (operator fayllari)
    path(
        "patients/documents/responses/my/",
        PatientResponseListView.as_view(),
        name="patient-response-list"
    ),

    # ============================================================
    # 👤 PROFILE
    # ============================================================
    path(
        "me/profile/",
        MeProfileView.as_view(),
        name="me-profile"
    ),

    # ✅ 2. KEYIN - Router (oxirida)
    path("", include(router.urls)),
]
