from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import (
    Country, City, Accreditation, Specialty, Clinic, WorldClinic
)
from .serializers import (
    CountrySerializer, CitySerializer, AccreditationSerializer, SpecialtySerializer,
    ClinicCardSerializer, ClinicDetailSerializer, DoctorSerializer,
    TreatmentPriceSerializer, ClinicInfrastructureSerializer, ClinicImageSerializer,
    NearbyStaySerializer, WorldClinicSerializer
)

# ======================================
# Reference endpoints (faqat GET)
# ======================================

class CountryViewSet(viewsets.ReadOnlyModelViewSet):
    """Mamlakatlar ro'yxati"""
    queryset = Country.objects.all().order_by("title_uz")
    serializer_class = CountrySerializer

    @swagger_auto_schema(operation_summary="Mamlakatlar ro'yxati", operation_description="Barcha mamlakatlar", tags=["countries"])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Mamlakat detali", operation_description="Bitta mamlakat ma'lumotlari", tags=["countries"])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


class CityViewSet(viewsets.ReadOnlyModelViewSet):
    """Shaharlar ro'yxati"""
    serializer_class = CitySerializer

    def get_queryset(self):
        qs = City.objects.select_related("country").all().order_by("title_uz")
        country_id = self.request.query_params.get("country")
        if country_id:
            qs = qs.filter(country_id=country_id)
        return qs

    @swagger_auto_schema(
        operation_summary="Shaharlar ro'yxati",
        operation_description="Shaharlar, country bo'yicha filter",
        manual_parameters=[openapi.Parameter("country", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Country ID")],
        tags=["cities"]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Shahar detali", operation_description="Bitta shahar ma'lumotlari", tags=["cities"])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


class AccreditationViewSet(viewsets.ReadOnlyModelViewSet):
    """Akkreditatsiya turlari"""
    queryset = Accreditation.objects.all().order_by("code")
    serializer_class = AccreditationSerializer

    @swagger_auto_schema(operation_summary="Akkreditatsiyalar ro'yxati", operation_description="Barcha akkreditatsiya turlari", tags=["accreditations"])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Akkreditatsiya detali", operation_description="Bitta akkreditatsiya", tags=["accreditations"])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


class SpecialtyViewSet(viewsets.ReadOnlyModelViewSet):
    """Mutaxassisliklar"""
    queryset = Specialty.objects.filter(is_active=True).order_by("title_uz")
    serializer_class = SpecialtySerializer

    @swagger_auto_schema(operation_summary="Mutaxassisliklar ro'yxati", operation_description="Barcha faol mutaxassisliklar", tags=["specialties"])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Mutaxassislik detali", operation_description="Bitta mutaxassislik", tags=["specialties"])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


# ======================================
# Clinics (faqat GET)
# ======================================

class ClinicViewSet(viewsets.ReadOnlyModelViewSet):
    """Klinikalar ro'yxati va detali (faqat GET)"""
    filter_backends = [filters.SearchFilter]
    search_fields = ["title_uz", "title_ru", "title_en", "address_uz", "address_ru", "address_en"]

    def get_queryset(self):
        qs = Clinic.objects.select_related("country", "city").prefetch_related("accreditations", "specialties")
        # filter params
        country = self.request.query_params.get("country")
        city = self.request.query_params.get("city")
        specialty = self.request.query_params.get("specialty")
        if country:
            qs = qs.filter(country_id=country)
        if city:
            qs = qs.filter(city_id=city)
        if specialty:
            qs = qs.filter(specialties__id=specialty)
        return qs.filter(is_active=True).order_by("-rating", "title_uz").distinct()

    def get_serializer_class(self):
        return ClinicDetailSerializer if self.action == "retrieve" else ClinicCardSerializer

    @swagger_auto_schema(
        operation_summary="Klinikalar ro‘yxati (filter bilan)",
        tags=["clinics"],
        manual_parameters=[
            openapi.Parameter("country", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Country ID"),
            openapi.Parameter("city", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="City ID"),
            openapi.Parameter("specialty", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Specialty ID"),
            openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Title/address qidirish"),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Klinika detali",
        operation_description="Klinika to'liq ma'lumotlari - shifokorlar, narxlar, galereya bilan",
        tags=["clinics"],
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    # === Nested GET endpoints ===
    @swagger_auto_schema(operation_summary="Klinika shifokorlari", operation_description="Klinikaning barcha shifokorlari", tags=["clinics"])
    @action(detail=True, methods=["get"], url_path="doctors")
    def doctors(self, request, pk=None):
        clinic = self.get_object()
        specialty = request.query_params.get("specialty")
        qs = clinic.doctors.all().order_by("order", "id")
        if specialty:
            qs = qs.filter(specialty_id=specialty)
        return Response(DoctorSerializer(qs, many=True, context={"request": request}).data)

    @swagger_auto_schema(operation_summary="Klinika narxlari", operation_description="Klinikaning davolash narxlari", tags=["clinics"])
    @action(detail=True, methods=["get"], url_path="prices")
    def prices(self, request, pk=None):
        clinic = self.get_object()
        specialty = request.query_params.get("specialty")
        qs = clinic.prices.filter(is_active=True).order_by("order", "id")
        if specialty:
            qs = qs.filter(specialty_id=specialty)
        return Response(TreatmentPriceSerializer(qs, many=True, context={"request": request}).data)

    @swagger_auto_schema(operation_summary="Klinika infratuzilmasi", operation_description="Klinika infratuzilma punktlari", tags=["clinics"])
    @action(detail=True, methods=["get"], url_path="infrastructure")
    def infrastructure(self, request, pk=None):
        clinic = self.get_object()
        qs = clinic.infrastructure.all()
        return Response(ClinicInfrastructureSerializer(qs, many=True, context={"request": request}).data)

    @swagger_auto_schema(operation_summary="Klinika galereyasi", operation_description="Klinika rasmlari", tags=["clinics"])
    @action(detail=True, methods=["get"], url_path="gallery")
    def gallery(self, request, pk=None):
        clinic = self.get_object()
        qs = clinic.gallery.all()
        return Response(ClinicImageSerializer(qs, many=True, context={"request": request}).data)

    @swagger_auto_schema(operation_summary="Yaqin atrof hotellar", operation_description="Klinika yonidagi mehmonxonalar", tags=["clinics"])
    @action(detail=True, methods=["get"], url_path="nearby")
    def nearby(self, request, pk=None):
        clinic = self.get_object()
        qs = clinic.nearby_stays.all()
        return Response(NearbyStaySerializer(qs, many=True, context={"request": request}).data)


# ======================================
# Jahon Klinikalari (faqat GET)
# ======================================

class WorldClinicViewSet(viewsets.ReadOnlyModelViewSet):
    """Jahon klinikalari ro'yxati (faqat GET)"""
    serializer_class = WorldClinicSerializer

    def get_queryset(self):
        qs = WorldClinic.objects.select_related("country").filter(is_active=True).order_by("title_uz")
        country_id = self.request.query_params.get("country")
        if country_id:
            qs = qs.filter(country_id=country_id)
        return qs

    @swagger_auto_schema(
        operation_summary="Jahon klinikalari ro'yxati",
        operation_description="Jahondagi mashhur klinikalar",
        tags=["world-clinics"],
        manual_parameters=[
            openapi.Parameter("country", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Country ID"),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Jahon klinikasi detali",
        operation_description="Bitta jahon klinikasi ma'lumotlari",
        tags=["world-clinics"],
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


