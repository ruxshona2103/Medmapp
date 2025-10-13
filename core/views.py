from rest_framework import viewsets, status
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from django.db.models import Prefetch

from .models import Stage, Tag
from .serializers import StageSerializer, TagSerializer
from core.permissions import IsOperator
from patients.models import Patient


class StageViewSet(viewsets.ModelViewSet):
    """
    TZ 3.3: Bosqichlar (Stage) API
    - Operator yoki admin foydalanuvchilar uchun to‘liq CRUD
    - Har bir bosqich ichida unga tegishli bemorlar ro‘yxati (patients) chiqadi
    - 'Yangi' (id=1) bosqichni o‘chirib bo‘lmaydi
    """
    serializer_class = StageSerializer
    permission_classes = [IsOperator]

    def get_queryset(self):
        # Har bir bosqichni unga tegishli bemorlar bilan birga olish
        return Stage.objects.prefetch_related(
            Prefetch("patients", queryset=Patient.objects.all().order_by("-created_at"))
        ).order_by("order", "id")

    @swagger_auto_schema(operation_description="Barcha bosqichlar ro‘yxati (order bo‘yicha tartiblangan).")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(operation_description="Yangi bosqich yaratish (faqat operator yoki admin uchun).")
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(operation_description="Bosqich ma’lumotlarini o‘zgartirish (PATCH).")
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(operation_description="Bosqichni o‘chirish (faqat operator yoki admin uchun).")
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # “Yangi” bosqichni o‘chirib bo‘lmaydi
        if instance.id == 1 or instance.code_name == "new":
            return Response(
                {"detail": "‘Yangi’ bosqichni o‘chirib bo‘lmaydi."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


class TagViewSet(viewsets.ModelViewSet):
    """
    TZ 3.2: Teglar (Tag) API
    - Operator yoki admin foydalanuvchilar uchun CRUD
    - GET /tags/ — barcha teglar ro‘yxati
    - POST /tags/ — yangi teg yaratish
    - DELETE /tags/{id}/ — tegni o‘chirish
    """
    queryset = Tag.objects.all().order_by("id")
    serializer_class = TagSerializer
    permission_classes = [IsOperator]
    http_method_names = ["get", "post", "delete"]

    @swagger_auto_schema(operation_description="Barcha teglar ro‘yxatini olish.")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(operation_description="Yangi teg yaratish (faqat operator yoki admin uchun).")
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(operation_description="Tegni o‘chirish (ID bo‘yicha).")
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
