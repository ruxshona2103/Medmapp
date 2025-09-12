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
    queryset = Clinic.objects.all().order_by("name")
    serializer_class = ClinicSerializer

    @action(detail=True, methods=["get"])
    def doctors(self, request, pk=None):
        qs = User.objects.filter(role="doctor", doctor_clinic__clinic_id=pk)
        page = self.paginate_queryset(qs)
        ser = DoctorSerializer(page or qs, many=True)
        return self.get_paginated_response(ser.data) if page is not None else Response(ser.data)

    @action(detail=True, methods=["get"])
    def reviews(self, request, pk=None):
        qs = Review.objects.filter(clinic_id=pk)
        page = self.paginate_queryset(qs)
        ser = ReviewSerializer(page or qs, many=True, context={"request": request})
        return self.get_paginated_response(ser.data) if page is not None else Response(ser.data)

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        qs = Review.objects.filter(clinic_id=pk)
        avg = round(qs.aggregate(a=Avg("rating"))["a"] or 0, 1)
        count = qs.count()
        dist = {i: 0 for i in range(1, 6)}
        for r in qs.values("rating").annotate(c=Count("id")):
            dist[r["rating"]] = r["c"]
        return Response({"rating": avg, "count": count, "distribution": dist})


class DoctorViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DoctorSerializer

    def get_queryset(self):
        qs = User.objects.filter(role="doctor")
        clinic_id = self.request.query_params.get("clinic")
        if clinic_id:
            qs = qs.filter(doctor_clinic__clinic_id=clinic_id)
        return qs.order_by("first_name", "last_name")

    @action(detail=True, methods=["get"])
    def reviews(self, request, pk=None):
        qs = Review.objects.filter(doctor_id=pk)
        page = self.paginate_queryset(qs)
        ser = ReviewSerializer(page or qs, many=True, context={"request": request})
        return self.get_paginated_response(ser.data) if page is not None else Response(ser.data)

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        qs = Review.objects.filter(doctor_id=pk)
        avg = round(qs.aggregate(a=Avg("rating"))["a"] or 0, 1)
        count = qs.count()
        dist = {i: 0 for i in range(1, 6)}
        for r in qs.values("rating").annotate(c=Count("id")):
            dist[r["rating"]] = r["c"]
        return Response({"rating": avg, "count": count, "distribution": dist})


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly & IsPatientToCreate]
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        clinic_id = self.request.query_params.get("clinic")
        doctor_id = self.request.query_params.get("doctor")
        if clinic_id:
            qs = qs.filter(clinic_id=clinic_id)
        if doctor_id:
            qs = qs.filter(doctor_id=doctor_id)
        return qs
