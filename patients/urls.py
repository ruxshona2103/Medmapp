from django.urls import path
from .views import (
    PatientProfileListView,
    PatientListView,
    PatientCreateView,
    PatientMeView,
    OperatorMeView,
    ChangeStageView,
    PatientDocumentCreateView,
    PatientDocumentDeleteView,
    StageListView,
    TagListView,
    TagDeleteView,
)

urlpatterns = [
    # Profil va bemorlar
    path("profiles/", PatientProfileListView.as_view(), name="patient-profile-list"),
    path("", PatientListView.as_view(), name="patient-list"),
    path("create/", PatientCreateView.as_view(), name="patient-create"),
    path("me/", PatientMeView.as_view(), name="patient-me"),

    # Operator
    path("operators/me/", OperatorMeView.as_view(), name="operator-me"),

    # Bosqich
    path("<int:patient_id>/change-stage/", ChangeStageView.as_view(), name="change-stage"),

    # Hujjatlar
    path("<int:patient_id>/documents/", PatientDocumentCreateView.as_view(), name="patient-document-create"),
    path("documents/<int:pk>/", PatientDocumentDeleteView.as_view(), name="patient-document-delete"),

    # Stage va Tag
    path("stages/", StageListView.as_view(), name="stage-list"),
    path("tags/", TagListView.as_view(), name="tag-list"),
    path("tags/<int:pk>/", TagDeleteView.as_view(), name="tag-delete"),
]
