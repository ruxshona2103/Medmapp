from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView,TokenVerifyView  # ✅ to‘g‘ri


from .views import (
    UserViewSet,
    OtpRequestView,
    OtpVerifyView,
    RegisterView,
    LoginView,
    MedicalFileListView,
    MedicalFileUploadView, OperatorLoginView, OperatorTokenRefreshView, PartnerLoginView, PartnerTokenRefreshView,
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')

urlpatterns = [
    path("auth/operator/login/", OperatorLoginView.as_view(), name="operator_login"),
    path("auth/operator/refresh/", OperatorTokenRefreshView.as_view(), name="operator_refresh"),

    path('partner/login/', PartnerLoginView.as_view(), name='partner-login'),
    path('partner/refresh/', PartnerTokenRefreshView.as_view(), name='partner-refresh'),

    # OTP auth
    path("auth/request-otp/", OtpRequestView.as_view(), name="request-otp"),
    path("auth/verify-otp/", OtpVerifyView.as_view(), name="verify-otp"),

    # Register & Login
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),

    # JWT token endpoints
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/verify/", TokenVerifyView.as_view(), name="token_verify"),


    # Users & medical files
    path("", include(router.urls)),
    path("users/<int:pk>/medical-files/", MedicalFileListView.as_view(), name="medical-files"),
    path("users/<int:pk>/medical-files/upload/", MedicalFileUploadView.as_view(), name="medical-files-upload"),
]
