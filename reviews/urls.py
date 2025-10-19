from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ClinicViewSet, DoctorViewSet, ReviewViewSet
router = DefaultRouter()
router.register(r"clinics", ClinicViewSet, basename="clinics")
router.register(r"doctors", DoctorViewSet, basename="doctors")
router.register(r"reviews", ReviewViewSet, basename="reviews")

urlpatterns = [
    path("", include(router.urls)),
]
