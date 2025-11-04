from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CountryViewSet, CityViewSet, SpecialtyViewSet,
    ClinicViewSet, DoctorViewSet, TreatmentPriceViewSet,
    ClinicImageViewSet, ClinicInfrastructureViewSet, NearbyStayViewSet,
)

router = DefaultRouter()
router.register(r"countries", CountryViewSet, basename="countries")
router.register(r"cities", CityViewSet, basename="cities")
router.register(r"specialties", SpecialtyViewSet, basename="specialties")

router.register(r"clinics", ClinicViewSet, basename="clinics")
router.register(r"doctors", DoctorViewSet, basename="doctors")
router.register(r"prices", TreatmentPriceViewSet, basename="prices")
router.register(r"gallery", ClinicImageViewSet, basename="gallery")
router.register(r"infrastructure", ClinicInfrastructureViewSet, basename="infrastructure")
router.register(r"nearby", NearbyStayViewSet, basename="nearby")

urlpatterns = [path("", include(router.urls))]
