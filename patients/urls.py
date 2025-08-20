from django.urls import path
from .views import PatientProfileView

urlpatterns = [
    path("profile/me/", PatientProfileView.as_view(), name="patient-profile"),
]
