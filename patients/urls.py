# patients/urls.py
from django.urls import path
from .views import (
    ConsultationFormView,
    PatientListView,
    PatientCreateView,
    PatientMeView,
    OperatorMeView,
    PatientDocumentCreateView,
    PatientDocumentDeleteView,
    PatientAvatarUpdateView,
    PatientDeleteView,
)

urlpatterns = [
    path("", PatientListView.as_view(), name="patient-list"),
    path("consultation/", ConsultationFormView.as_view(), name="consultation-form"),
    path("create/", PatientCreateView.as_view(), name="patient-create"),
    path("me/", PatientMeView.as_view(), name="patient-me"),
    path("operators/me/", OperatorMeView.as_view(), name="operator-me"),
    path("<int:patient_id>/documents/", PatientDocumentCreateView.as_view(), name="document-create"),
    path("documents/<int:pk>/", PatientDocumentDeleteView.as_view(), name="document-delete"),
    path("avatar/", PatientAvatarUpdateView.as_view(), name="avatar-update"),
    path("delete/", PatientDeleteView.as_view(), name="patient-delete"),
]