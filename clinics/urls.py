from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CountryViewSet, CityViewSet, SpecialtyViewSet,
    ClinicViewSet, WorldClinicViewSet,
)

router = DefaultRouter()
router.register(r"countries", CountryViewSet, basename="countries")
router.register(r"cities", CityViewSet, basename="cities")
router.register(r"specialties", SpecialtyViewSet, basename="specialties")

router.register(r"clinics", ClinicViewSet, basename="clinics")
router.register(r"world-clinics", WorldClinicViewSet, basename="world-clinics")
urlpatterns = [path("", include(router.urls))]
