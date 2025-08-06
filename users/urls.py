from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView, LoginView, LogoutView,
    UserViewSet, MedicalFileUploadView, MedicalFileListView
)
from rest_framework_simplejwt.views import (
    TokenRefreshView, TokenObtainPairView, TokenVerifyView
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')

urlpatterns = [
    path('auth/register/', RegisterView.as_view()),
    path('auth/login/', LoginView.as_view()),
    path('auth/logout/', LogoutView.as_view()),
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('', include(router.urls)),
    path('users/<int:pk>/medical-files/', MedicalFileListView.as_view()),
    path('users/<int:pk>/medical-files/upload/', MedicalFileUploadView.as_view()),
]
