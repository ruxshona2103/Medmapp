from django.urls import path
from .views import OtpRequestView, OtpVerifyView

urlpatterns = [
    path("auth/request-otp/", OtpRequestView.as_view(), name="request-otp"),
    path("auth/verify-otp/", OtpVerifyView.as_view(), name="verify-otp"),
]
