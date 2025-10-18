from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Clinic, Review
from .serializers import ClinicSerializer, DoctorSerializer, ReviewSerializer

User = get_user_model()


# ===============================================================
# 📄 Dinamik pagination class (per_page qo‘llab-quvvatlaydi)
# ===============================================================
class CustomPagination(PageNumberPagination):
    page_size = 10  # default
    page_size_query_param = "per_page"  # front orqali o‘zgartirish uchun
    max_page_size = 100


# ===============================================================
# 🏥 Klinikalar – full filter + pagination
# ===============================================================
class ClinicViewSet(viewsets.ReadOnlyModelViewSet):
    """
    🏥 Klinikalar API
    - Klinikalar ro‘yxati (search, city, speciality filter bilan)
    - Pagination: page, per_page
    """
    queryset = Clinic.objects.all().order_by("name")
    serializer_class = ClinicSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = CustomPagination

    @swagger_auto_schema(
        operation_summary="🏥 Klinikalar ro‘yxatini olish (filter va pagination bilan)",
        operation_description=(
            "Filtrlash va pagination parametrlari:\n"
            "- `search`: Klinika nomi yoki manzili bo‘yicha qidirish\n"
            "- `city`: Shahar nomi bo‘yicha filter\n"
            "- `speciality`: Mutaxassislik nomi bo‘yicha filter\n"
            "- `page`: Sahifa raqami (default: 1)\n"
            "- `per_page`: Har bir sahifadagi elementlar soni (default: 10)"
        ),
        manual_parameters=[
            openapi.Parameter(
                "search", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                description="Klinika nomi yoki manzili bo‘yicha qidirish"
            ),
            openapi.Parameter(
                "city", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                description="Shahar nomi bo‘yicha filter (masalan: Tashkent)"
            ),
            openapi.Parameter(
                "speciality", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                description="Mutaxassislik bo‘yicha filter (masalan: Kardiologiya)"
            ),
            openapi.Parameter(
                "page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                description="Sahifa raqami (pagination)"
            ),
            openapi.Parameter(
                "per_page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                description="Sahifadagi elementlar soni (pagination)"
            ),
        ],
        responses={200: ClinicSerializer(many=True)},
        tags=["clinics"],
    )
    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()

        # 🔍 Qidiruv
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(address__icontains=search))

        # 🏙️ Shahar bo‘yicha filter
        city = request.query_params.get("city")
        if city:
            qs = qs.filter(address__icontains=city)

        # ⚕️ Mutaxassislik bo‘yicha filter
        speciality = request.query_params.get("speciality")
        if speciality:
            clinic_ids = User.objects.filter(
                role="doctor",
                doctor_clinic__clinic__isnull=False,
                speciality__icontains=speciality,
            ).values_list("doctor_clinic__clinic_id", flat=True)
            qs = qs.filter(id__in=clinic_ids)

        # 📄 Pagination (page + per_page)
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page or qs, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data) if page else Response(serializer.data)

    # ===========================================================
    # 👨‍⚕️ Klinikadagi shifokorlar
    # ===========================================================
    @action(detail=True, methods=["get"], url_path="doctors")
    def doctors(self, request, pk=None):
        doctors = User.objects.filter(role="doctor", doctor_clinic__clinic_id=pk)
        page = self.paginate_queryset(doctors)
        serializer = DoctorSerializer(page or doctors, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data) if page else Response(serializer.data)

    # ===========================================================
    # 💬 Klinikadagi sharhlar
    # ===========================================================
    @action(detail=True, methods=["get"], url_path="reviews")
    def reviews(self, request, pk=None):
        reviews = Review.objects.filter(clinic_id=pk)
        page = self.paginate_queryset(reviews)
        serializer = ReviewSerializer(page or reviews, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data) if page else Response(serializer.data)

    # ===========================================================
    # ⭐ Klinikaga oid umumiy reyting ma’lumotlari
    # ===========================================================
    @action(detail=True, methods=["get"], url_path="summary")
    def summary(self, request, pk=None):
        reviews = Review.objects.filter(clinic_id=pk)
        avg_rating = round(reviews.aggregate(a=Avg("rating"))["a"] or 0, 1)
        count = reviews.count()

        distribution = {i: 0 for i in range(1, 6)}
        for row in reviews.values("rating").annotate(c=Count("id")):
            distribution[row["rating"]] = row["c"]

        return Response({
            "rating": avg_rating,
            "count": count,
            "distribution": distribution,
        })

# ===============================================================
# 👨‍⚕️ Shifokorlar
# ===============================================================
class DoctorViewSet(viewsets.ReadOnlyModelViewSet):
    """
    👨‍⚕️ Shifokorlar API
    - Shifokorlar ro‘yxati (klinikaga qarab)
    - Sharhlar va reytinglar
    """
    serializer_class = DoctorSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = User.objects.filter(role="doctor").select_related("doctor_clinic__clinic")
        clinic_id = self.request.query_params.get("clinic")
        if clinic_id:
            qs = qs.filter(doctor_clinic__clinic_id=clinic_id)
        return qs.order_by("first_name", "last_name")

    def list(self, request, *args, **kwargs):
        doctors = self.get_queryset()
        serializer = self.get_serializer(doctors, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="reviews")
    def reviews(self, request, pk=None):
        """
        💬 Shifokorga yozilgan sharhlar
        """
        qs = Review.objects.filter(doctor_id=pk)
        page = self.paginate_queryset(qs)
        serializer = ReviewSerializer(page or qs, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data) if page else Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="summary")
    def summary(self, request, pk=None):
        """
        ⭐ Shifokor reytingining umumiy ko‘rinishi
        """
        qs = Review.objects.filter(doctor_id=pk)
        avg = round(qs.aggregate(a=Avg("rating"))["a"] or 0, 1)
        count = qs.count()
        dist = {i: 0 for i in range(1, 6)}
        for r in qs.values("rating").annotate(c=Count("id")):
            dist[r["rating"]] = r["c"]
        return Response({"rating": avg, "count": count, "distribution": dist})


# ===============================================================
# 💬 Sharhlar
# ===============================================================
class ReviewViewSet(viewsets.ReadOnlyModelViewSet):
    """
    💬 Sharhlar (Clinic yoki Doctor bo‘yicha o‘qish uchun)
    """
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    queryset = Review.objects.all().select_related("clinic", "doctor", "author")

    def get_queryset(self):
        qs = super().get_queryset()
        clinic_id = self.request.query_params.get("clinic")
        doctor_id = self.request.query_params.get("doctor")

        if clinic_id:
            qs = qs.filter(clinic_id=clinic_id)
        if doctor_id:
            qs = qs.filter(doctor_id=doctor_id)

        return qs.order_by("-created_at")

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        serializer = ReviewSerializer(page or qs, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data) if page else Response(serializer.data)
