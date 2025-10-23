from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Q
from rest_framework import viewsets, status
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
# 📄 Dinamik pagination class (per_page qo'llab-quvvatlaydi)
# ===============================================================
class CustomPagination(PageNumberPagination):
    page_size = 10  # default
    page_size_query_param = "per_page"  # front orqali o'zgartirish uchun
    max_page_size = 100


# ===============================================================
# 🏥 Klinikalar – filterlar, pagination, statistika
# ===============================================================
class ClinicViewSet(viewsets.ReadOnlyModelViewSet):
    """
    🏥 Klinikalar API
    - Klinikalar ro'yxati (address, working hours, speciality filter bilan)
    - Pagination (page, per_page)
    - Statistik ma'lumotlar: jami klinikalar, mutaxassislar soni, o'rtacha reyting
    """
    queryset = Clinic.objects.all().order_by("name")
    serializer_class = ClinicSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = CustomPagination

    # ===========================================================
    # 🔍 Klinikalar ro'yxati (filter + pagination)
    # ===========================================================
    @swagger_auto_schema(
        operation_summary="🏥 Klinikalar ro'yxatini olish (filter va pagination bilan)",
        operation_description=(
                "Filtrlash va pagination parametrlari:\n\n"
                "- `search`: Klinika nomi yoki manzili bo'yicha qidirish\n"
                "- `address`: Manzil bo'yicha filter (masalan: Tashkent)\n"
                "- `speciality`: Mutaxassislik bo'yicha filter (masalan: Kardiologiya)\n"
                "- `working_hours_from`: Ish soatining boshlanish vaqti (masalan: 09:00)\n"
                "- `working_hours_to`: Ish soatining tugash vaqti (masalan: 18:00)\n"
                "- `page`: Sahifa raqami (default: 1)\n"
                "- `per_page`: Har bir sahifadagi elementlar soni (default: 10)"
        ),
        manual_parameters=[
            openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description="Klinika nomi yoki manzili bo'yicha qidirish"),
            openapi.Parameter("address", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description="Manzil bo'yicha filter (masalan: Tashkent)"),
            openapi.Parameter("speciality", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description="Mutaxassislik bo'yicha filter (masalan: Kardiologiya)"),
            openapi.Parameter("working_hours_from", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description="Ish soatining boshlanish vaqti (masalan: 09:00)"),
            openapi.Parameter("working_hours_to", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description="Ish soatining tugash vaqti (masalan: 18:00)"),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description="Sahifa raqami (pagination)"),
            openapi.Parameter("per_page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description="Sahifadagi elementlar soni (pagination)"),
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

        # 🏙️ Manzil bo'yicha filter
        address = request.query_params.get("address")
        if address:
            qs = qs.filter(address__icontains=address)

        # ⚕️ Mutaxassislik bo'yicha filter
        speciality = request.query_params.get("speciality")
        if speciality:
            clinic_ids = User.objects.filter(
                role="doctor",
                doctor_clinic__clinic__isnull=False,
                specialties__icontains=speciality,
            ).values_list("doctor_clinic__clinic_id", flat=True).distinct()
            qs = qs.filter(id__in=clinic_ids)

        # ⏰ Ish vaqti (from-to) filtrini qo'shish
        working_hours_from = request.query_params.get("working_hours_from")
        working_hours_to = request.query_params.get("working_hours_to")
        if working_hours_from and working_hours_to:
            # workingHours field'ini tekshiring - agar JSONField yoki CharField bo'lsa
            # to'g'ri filter logikasini yozing
            qs = qs.filter(workingHours__gte=working_hours_from, workingHours__lte=working_hours_to)

        # 📄 Pagination (page + per_page)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

    # ===========================================================
    # 📊 Statistik ma'lumotlar (Jami klinikalar, mutaxassislar, reyting)
    # ===========================================================
    @swagger_auto_schema(
        operation_summary="📊 Klinikalar bo'yicha umumiy statistika olish",
        operation_description=(
                "Platformadagi klinikalar soni, barcha mutaxassislar soni va o'rtacha reytingni qaytaradi.\n\n"
                "**Qaytadigan natija:**\n"
                "- `total_clinics`: Jami klinikalar soni\n"
                "- `total_specialists`: Platformadagi barcha shifokorlar soni\n"
                "- `average_rating`: Klinikalar bo'yicha o'rtacha reyting (1 dan 5 gacha)"
        ),
        responses={
            200: openapi.Response(
                description="Statistik ma'lumotlar muvaffaqiyatli qaytarildi",
                examples={"application/json": {"total_clinics": 5, "total_specialists": 250, "average_rating": 4.7}},
            ),
        },
        tags=["clinics"],
    )
    @action(detail=False, methods=["get"], url_path="statistics")
    def statistics(self, request):
        total_clinics = Clinic.objects.count()
        total_specialists = User.objects.filter(role="doctor").count()
        average_rating = Clinic.objects.aggregate(avg=Avg("reviews__rating"))["avg"] or 0
        return Response({
            "total_clinics": total_clinics,
            "total_specialists": total_specialists,
            "average_rating": round(average_rating, 1),
        })

    # ===========================================================
    # 👨‍⚕️ Klinikadagi shifokorlar
    # ===========================================================
    @swagger_auto_schema(
        operation_summary="👨‍⚕️ Klinikadagi shifokorlar ro'yxatini olish",
        operation_description="Berilgan klinikada ishlaydigan barcha shifokorlarni ro'yxatini qaytaradi",
        responses={200: DoctorSerializer(many=True)},
        tags=["clinics"],
    )
    @action(detail=True, methods=["get"], url_path="doctors")
    def doctors(self, request, pk=None):
        doctors = User.objects.filter(role="doctor", doctor_clinic__clinic_id=pk)
        page = self.paginate_queryset(doctors)
        serializer = DoctorSerializer(page or doctors, many=True, context={"request": request})

        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    # ===========================================================
    # 💬 Klinikadagi sharhlar
    # ===========================================================
    @swagger_auto_schema(
        operation_summary="💬 Klinikaga yozilgan sharhlar ro'yxatini olish",
        operation_description="Berilgan klinika uchun yozilgan barcha sharhlarni qaytaradi",
        responses={200: ReviewSerializer(many=True)},
        tags=["clinics"],
    )
    @action(detail=True, methods=["get"], url_path="reviews")
    def reviews(self, request, pk=None):
        reviews = Review.objects.filter(clinic_id=pk).order_by("-created_at")
        page = self.paginate_queryset(reviews)
        serializer = ReviewSerializer(page or reviews, many=True, context={"request": request})

        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    # ===========================================================
    # ⭐ Klinikaga oid umumiy reyting ma'lumotlari
    # ===========================================================
    @swagger_auto_schema(
        operation_summary="⭐ Klinikaga oid umumiy reyting ma'lumotlarini olish",
        operation_description="Klinikaning o'rtacha reytingi, sharhlar soni va reyting taqsimotini qaytaradi",
        responses={
            200: openapi.Response(
                description="Reyting ma'lumotlari",
                examples={
                    "application/json": {
                        "rating": 4.5,
                        "count": 150,
                        "distribution": {1: 5, 2: 10, 3: 20, 4: 50, 5: 65}
                    }
                }
            )
        },
        tags=["clinics"],
    )
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
    - Shifokorlar ro'yxati (klinikaga qarab)
    - Sharhlar va reytinglar
    """
    serializer_class = DoctorSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = CustomPagination

    def get_queryset(self):
        qs = User.objects.filter(role="doctor").select_related("doctor_clinic__clinic")
        clinic_id = self.request.query_params.get("clinic")
        if clinic_id:
            qs = qs.filter(doctor_clinic__clinic_id=clinic_id)
        return qs.order_by("first_name", "last_name")

    @swagger_auto_schema(
        operation_summary="👨‍⚕️ Shifokorlar ro'yxatini olish",
        operation_description="Barcha shifokorlar yoki klinikaga qarab filtrlangan shifokorlar ro'yxati",
        manual_parameters=[
            openapi.Parameter("clinic", openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description="Klinika ID bo'yicha filter"),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Sahifa raqami"),
            openapi.Parameter("per_page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description="Sahifadagi elementlar soni"),
        ],
        responses={200: DoctorSerializer(many=True)},
        tags=["doctors"],
    )
    def list(self, request, *args, **kwargs):
        doctors = self.get_queryset()
        page = self.paginate_queryset(doctors)
        serializer = self.get_serializer(page or doctors, many=True, context={"request": request})

        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_summary="💬 Shifokorga yozilgan sharhlar",
        operation_description="Berilgan shifokor uchun yozilgan barcha sharhlar",
        responses={200: ReviewSerializer(many=True)},
        tags=["doctors"],
    )
    @action(detail=True, methods=["get"], url_path="reviews")
    def reviews(self, request, pk=None):
        qs = Review.objects.filter(doctor_id=pk).order_by("-created_at")
        page = self.paginate_queryset(qs)
        serializer = ReviewSerializer(page or qs, many=True, context={"request": request})

        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_summary="⭐ Shifokor reytingining umumiy ko'rinishi",
        operation_description="Shifokorning o'rtacha reytingi, sharhlar soni va reyting taqsimoti",
        responses={
            200: openapi.Response(
                description="Reyting ma'lumotlari",
                examples={
                    "application/json": {
                        "rating": 4.8,
                        "count": 75,
                        "distribution": {1: 2, 2: 3, 3: 10, 4: 20, 5: 40}
                    }
                }
            )
        },
        tags=["doctors"],
    )
    @action(detail=True, methods=["get"], url_path="summary")
    def summary(self, request, pk=None):
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
    💬 Sharhlar (Clinic yoki Doctor bo'yicha o'qish uchun)
    """
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = CustomPagination
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

    @swagger_auto_schema(
        operation_summary="💬 Sharhlar ro'yxatini olish",
        operation_description="Klinika yoki shifokor bo'yicha filtrlangan sharhlar ro'yxati",
        manual_parameters=[
            openapi.Parameter("clinic", openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description="Klinika ID bo'yicha filter"),
            openapi.Parameter("doctor", openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description="Shifokor ID bo'yicha filter"),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Sahifa raqami"),
            openapi.Parameter("per_page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description="Sahifadagi elementlar soni"),
        ],
        responses={200: ReviewSerializer(many=True)},
        tags=["reviews"],
    )
    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        serializer = ReviewSerializer(page or qs, many=True, context={"request": request})

        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)