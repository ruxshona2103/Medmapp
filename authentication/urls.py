from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView
from .views import *


router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')

urlpatterns = [
    path("auth/request-otp/", OtpRequestView.as_view(), name="request-otp"),
    path("auth/verify-otp/", OtpVerifyView.as_view(), name="verify-otp"),
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("", include(router.urls)),
    path("users/<int:pk>/medical-files/", MedicalFileListView.as_view(), name="medical-files"),
    path("users/<int:pk>/medical-files/upload/", MedicalFileUploadView.as_view(), name="medical-files-upload"),
]
