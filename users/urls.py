from django.urls import path, include
from rest_framework.routers import DefaultRouter

from departments.urls import urlpatterns
from .views import UserViewSet


router = DefaultRouter()
router.register(r'users', UserViewSet)

urlpatterns = [
    path('', include(router.urls))
]