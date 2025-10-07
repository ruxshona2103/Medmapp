from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PatientViewSet,
    PatientDocumentViewSet,
    ResponseLettersViewSet,
    ContractApproveViewSet,
    MeProfileView,
)

router = DefaultRouter()
router.register(r"patients", PatientViewSet, basename="patient")
router.register(r"response-letters", ResponseLettersViewSet, basename="response-letters")
router.register(r"contracts", ContractApproveViewSet, basename="contracts")

urlpatterns = [
    path("", include(router.urls)),
    path("patients/<int:patient_pk>/documents/", PatientDocumentViewSet.as_view({"post": "create"}), name="patient-docs-create"),
    path("documents/<int:pk>/", PatientDocumentViewSet.as_view({"delete": "destroy"}), name="patient-docs-delete"),
    path("me/profile/", MeProfileView.as_view(), name="me-profile"),
]
