from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ClinicViewSet, DoctorViewSet, ReviewViewSet

router = DefaultRouter()
router.register(r"clinics", ClinicViewSet, basename="clinic")
router.register(r"doctors", DoctorViewSet, basename="doctor")
router.register(r"reviews", ReviewViewSet, basename="review")

urlpatterns = [path("", include(router.urls))]
