from django.contrib.auth import get_user_model
from django.db.models import Avg, Count
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .models import Clinic, Review
from .serializers import ClinicSerializer, DoctorSerializer, ReviewSerializer
from .permissions import IsPatientToCreate

User = get_user_model()


class ClinicViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Klinikalar ro‘yxatini olish va har bir klinikaga tegishli shifokorlar,
    izohlar va baholarni ko‘rish uchun ViewSet.
    Swagger hujjat generatsiyasida xatolik chiqmasligi uchun xavfsiz.
    """

    queryset = Clinic.objects.all().order_by("name")
    serializer_class = ClinicSerializer

    @action(detail=True, methods=["get"], description="Klinikaga tegishli shifokorlar ro‘yxatini olish")
    def doctors(self, request, pk=None):
        if getattr(self, "swagger_fake_view", False):
            return Response([])

        qs = User.objects.filter(role="doctor", doctor_clinic__clinic_id=pk)
        page = self.paginate_queryset(qs)
        serializer = DoctorSerializer(page or qs, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data) if page else Response(serializer.data)

    @action(detail=True, methods=["get"], description="Klinikaga berilgan izohlar (review) ro‘yxatini olish")
    def reviews(self, request, pk=None):
        if getattr(self, "swagger_fake_view", False):
            return Response([])

        qs = Review.objects.filter(clinic_id=pk)
        page = self.paginate_queryset(qs)
        serializer = ReviewSerializer(page or qs, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data) if page else Response(serializer.data)

    @action(detail=True, methods=["get"], description="Klinika baholarining umumiy statistikasi")
    def summary(self, request, pk=None):
        if getattr(self, "swagger_fake_view", False):
            return Response({
                "rating": 0,
                "count": 0,
                "distribution": {i: 0 for i in range(1, 6)}
            })

        qs = Review.objects.filter(clinic_id=pk)
        avg_rating = round(qs.aggregate(a=Avg("rating"))["a"] or 0, 1)
        total_reviews = qs.count()

        distribution = {i: 0 for i in range(1, 6)}
        for item in qs.values("rating").annotate(c=Count("id")):
            distribution[item["rating"]] = item["c"]

        return Response({
            "rating": avg_rating,
            "count": total_reviews,
            "distribution": distribution
        })


class DoctorViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Shifokorlar ro‘yxatini olish va ularning izohlari hamda reytinglarini ko‘rish uchun ViewSet.
    """

    serializer_class = DoctorSerializer

    def get_queryset(self):
        qs = User.objects.filter(role="doctor")
        clinic_id = self.request.query_params.get("clinic")
        if clinic_id:
            qs = qs.filter(doctor_clinic__clinic_id=clinic_id)
        return qs.order_by("first_name", "last_name")

    @action(detail=True, methods=["get"], description="Shifokorga berilgan izohlar ro‘yxatini olish")
    def reviews(self, request, pk=None):
        if getattr(self, "swagger_fake_view", False):
            return Response([])

        qs = Review.objects.filter(doctor_id=pk)
        page = self.paginate_queryset(qs)
        serializer = ReviewSerializer(page or qs, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data) if page else Response(serializer.data)

    @action(detail=True, methods=["get"], description="Shifokor baholarining umumiy statistikasi")
    def summary(self, request, pk=None):
        if getattr(self, "swagger_fake_view", False):
            return Response({
                "rating": 0,
                "count": 0,
                "distribution": {i: 0 for i in range(1, 6)}
            })

        qs = Review.objects.filter(doctor_id=pk)
        avg_rating = round(qs.aggregate(a=Avg("rating"))["a"] or 0, 1)
        total_reviews = qs.count()

        distribution = {i: 0 for i in range(1, 6)}
        for item in qs.values("rating").annotate(c=Count("id")):
            distribution[item["rating"]] = item["c"]

        return Response({
            "rating": avg_rating,
            "count": total_reviews,
            "distribution": distribution
        })


class ReviewViewSet(viewsets.ModelViewSet):
    """
    Foydalanuvchilar (asosan bemorlar) tomonidan klinika yoki shifokorga baho berish (review) uchun ViewSet.
    Swagger generatsiyasi va anonim userlar uchun xavfsiz ishlaydi.
    """

    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsPatientToCreate]

    def get_queryset(self):
        # Swagger hujjat generatsiyasida xatolik chiqmasligi uchun
        if getattr(self, "swagger_fake_view", False):
            return Review.objects.none()

        qs = Review.objects.all()
        clinic_id = self.request.query_params.get("clinic")
        doctor_id = self.request.query_params.get("doctor")

        if clinic_id:
            qs = qs.filter(clinic_id=clinic_id)
        if doctor_id:
            qs = qs.filter(doctor_id=doctor_id)

        return qs
