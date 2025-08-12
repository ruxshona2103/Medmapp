from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ApplicationViewSet, ServiceViewSet, OrderedServiceViewSet

router = DefaultRouter()
router.register(r'applications', ApplicationViewSet, basename="applications")
router.register(r'services', ServiceViewSet, basename="services")
router.register(r'ordered-services', OrderedServiceViewSet, basename="ordered-services")

urlpatterns = [
    path('', include(router.urls)),
]
