# patients/urls.py
from django.urls import path
from .views import (
    StageListView,
    TagListView,
    TagDeleteView,
    PatientListView,
    ApplicationCreateView,
    PatientCreateView,
    PatientMeView,
    OperatorMeView,
    ChangeStageView,
    PatientDocumentCreateView,
    PatientDocumentDeleteView,
    PatientAvatarUpdateView,
    PatientDeleteView,
)

urlpatterns = [
    path("stages/", StageListView.as_view(), name="stage-list"),
    path("tags/", TagListView.as_view(), name="tag-list"),
    path("tags/<int:pk>/", TagDeleteView.as_view(), name="tag-delete"),
    path("", PatientListView.as_view(), name="patient-list"),
    path("applications/", ApplicationCreateView.as_view(), name="application-create"),
    path("create/", PatientCreateView.as_view(), name="patient-create"),
    path("me/", PatientMeView.as_view(), name="patient-me"),
    path("operators/me/", OperatorMeView.as_view(), name="operator-me"),
    path("<int:patient_id>/change-stage/", ChangeStageView.as_view(), name="change-stage"),
    path("<int:patient_id>/documents/", PatientDocumentCreateView.as_view(), name="document-create"),
    path("documents/<int:pk>/", PatientDocumentDeleteView.as_view(), name="document-delete"),
    path("avatar/", PatientAvatarUpdateView.as_view(), name="avatar-update"),
    path("delete/", PatientDeleteView.as_view(), name="patient-delete"),
]