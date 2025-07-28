# yourapp/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DepartmentsViewSet, CustomTokenObtainPairView
from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()
router.register(r"departments", DepartmentsViewSet, basename="department")

urlpatterns = [
    path("", include(router.urls)),
    path("token/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
