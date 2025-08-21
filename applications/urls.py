from django.urls import path
from .views import ApplicationCreateView, ApplicationStatusView

urlpatterns = [
    path("application/create/", ApplicationCreateView.as_view(), name="application-create"),
    path("application/status/", ApplicationStatusView.as_view(), name="application-status"),
]
