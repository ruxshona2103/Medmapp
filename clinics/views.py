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
# 🔹 Reference endpoints (faqat GET)
# ======================================

class CountryViewSet(viewsets.ReadOnlyModelViewSet):
    """Mamlakatlar ro'yxati (faqat GET)"""
    queryset = Country.objects.all().order_by("title_uz")
    serializer_class = CountrySerializer


class CityViewSet(viewsets.ReadOnlyModelViewSet):
    """Shaharlar (faqat GET, country bo'yicha filterlanadi)"""
    serializer_class = CitySerializer

    def get_queryset(self):
        qs = City.objects.select_related("country").all().order_by("title_uz")
        country_id = self.request.query_params.get("country")
        if country_id:
            qs = qs.filter(country_id=country_id)
        return qs


class AccreditationViewSet(viewsets.ReadOnlyModelViewSet):
    """Akkreditatsiya turlari (faqat GET)"""
    queryset = Accreditation.objects.all().order_by("code")
    serializer_class = AccreditationSerializer


class SpecialtyViewSet(viewsets.ReadOnlyModelViewSet):
    """Mutaxassisliklar (faqat GET)"""
    queryset = Specialty.objects.filter(is_active=True).order_by("title_uz")
    serializer_class = SpecialtySerializer


# ======================================
# 🔹 Clinics (faqat GET, barcha nested GET’lar bilan)
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
        operation_summary="Klinika detali (bosh sahifa bloklari bilan)",
        tags=["clinics"],
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    # === Nested GET endpoints ===
    @swagger_auto_schema(operation_summary="Klinika shifokorlari", tags=["clinics"])
    @action(detail=True, methods=["get"], url_path="doctors")
    def doctors(self, request, pk=None):
        clinic = self.get_object()
        specialty = request.query_params.get("specialty")
        qs = clinic.doctors.all().order_by("order", "id")
        if specialty:
            qs = qs.filter(specialty_id=specialty)
        return Response(DoctorSerializer(qs, many=True, context={"request": request}).data)

    @swagger_auto_schema(operation_summary="Klinika narxlari", tags=["clinics"])
    @action(detail=True, methods=["get"], url_path="prices")
    def prices(self, request, pk=None):
        clinic = self.get_object()
        specialty = request.query_params.get("specialty")
        qs = clinic.prices.filter(is_active=True).order_by("order", "id")
        if specialty:
            qs = qs.filter(specialty_id=specialty)
        return Response(TreatmentPriceSerializer(qs, many=True, context={"request": request}).data)

    @swagger_auto_schema(operation_summary="Klinika infratuzilma punktlari", tags=["clinics"])
    @action(detail=True, methods=["get"], url_path="infrastructure")
    def infrastructure(self, request, pk=None):
        clinic = self.get_object()
        qs = clinic.infrastructure.all()
        return Response(ClinicInfrastructureSerializer(qs, many=True, context={"request": request}).data)

    @swagger_auto_schema(operation_summary="Klinika galereyasi", tags=["clinics"])
    @action(detail=True, methods=["get"], url_path="gallery")
    def gallery(self, request, pk=None):
        clinic = self.get_object()
        qs = clinic.gallery.all()
        return Response(ClinicImageSerializer(qs, many=True, context={"request": request}).data)

    @swagger_auto_schema(operation_summary="Yaqin atrof mehmon uylari / hotellar", tags=["clinics"])
    @action(detail=True, methods=["get"], url_path="nearby")
    def nearby(self, request, pk=None):
        clinic = self.get_object()
        qs = clinic.nearby_stays.all()
        return Response(NearbyStaySerializer(qs, many=True, context={"request": request}).data)


# ======================================
# 🔹 Jahon Klinikalari (faqat GET)
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
        tags=["world-clinics"],
        manual_parameters=[
            openapi.Parameter("country", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Country ID"),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Jahon klinikasi detali",
        tags=["world-clinics"],
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


