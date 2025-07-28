from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DepartmentsViewSet



router = DefaultRouter()
router.register(r"departments", DepartmentsViewSet, basename="department")

urlpatterns = [
    path("", include(router.urls))
]