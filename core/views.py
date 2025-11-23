from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.db import transaction
from django.db.models import Prefetch, Max
from .models import Stage, Tag
from .serializers import StageSerializer, TagSerializer
from patients.models import Patient


# ===============================================================
# 🧩 STAGE VIEWSET
# ===============================================================
class StageViewSet(viewsets.ModelViewSet):
    """
    🧩 Bosqichlar (Stage) API
    - Operator yoki admin foydalanuvchilar uchun to‘liq CRUD
    - Default tartib: avval `order`, so‘ng `id` bo‘yicha
    - Foydalanuvchi drag-drop orqali `order`ni o‘zgartirishi mumkin
    - 'Yangi' (id=1 yoki code_name='new') bosqichni o‘chirib bo‘lmaydi
    - Yangi bosqich yaratilganda avtomatik order belgilanadi
    """
    serializer_class = StageSerializer
    permission_classes = [permissions.IsAuthenticated]

    # ===========================================================
    # 📋 Bosqichlar ro‘yxati (default tartib: order -> id)
    # ===========================================================
    def get_queryset(self):
        qs = Stage.objects.prefetch_related(
            Prefetch("patients", queryset=Patient.objects.all().order_by("-created_at"))
        )

        # Agar order qiymati mavjud bo‘lsa — shu bo‘yicha tartibla
        if qs.filter(order__isnull=False).exists():
            return qs.order_by("order", "id")
        # Aks holda id bo‘yicha
        return qs.order_by("id")

    # ===========================================================
    # ➕ Yangi bosqich yaratish (avtomatik order)
    # ===========================================================
    def perform_create(self, serializer):
        last_order = Stage.objects.aggregate(max_order=Max("order"))["max_order"] or 0
        serializer.save(order=last_order + 1)

    # ===========================================================
    # 📋 Barcha bosqichlarni olish
    # ===========================================================
    @swagger_auto_schema(
        operation_summary="Barcha bosqichlar ro'yxati",
        operation_description="Bosqichlar ro'yxatini order bo'yicha tartiblangan holda qaytaradi",
        tags=["stages"]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    # ===========================================================
    # ➕ Yangi bosqich yaratish
    # ===========================================================
    @swagger_auto_schema(
        operation_summary="Yangi bosqich yaratish",
        operation_description="Yangi bosqich qo'shish",
        tags=["stages"]
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    # ===========================================================
    # ✏️ Bosqich ma’lumotlarini yangilash (PATCH)
    # ===========================================================
    @swagger_auto_schema(
        operation_summary="Bosqichni tahrirlash",
        operation_description="Bosqich nomi, rangi yoki boshqa atributlarini qisman yangilash",
        tags=["stages"]
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    # ===========================================================
    # 🗑️ Bosqichni o‘chirish
    # ===========================================================
    @swagger_auto_schema(
        operation_summary="Bosqichni o'chirish",
        operation_description="Yangi bosqichni o'chirib bo'lmaydi",
        tags=["stages"]
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.id == 1 or instance.code_name == "new":
            return Response(
                {"detail": "‘Yangi’ bosqichni o‘chirib bo‘lmaydi."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    # ===========================================================
    # 🔢 Bosqichlarni qayta tartiblash (ordering)
    # ===========================================================
    @swagger_auto_schema(
        operation_summary="Bosqichlarni qayta tartiblash",
        operation_description="Drag-drop orqali tartibni yangilash",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "order": openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_INTEGER), description="Bosqich ID'lari yangi tartibda"),
            },
            required=["order"],
        ),
        responses={200: "Tartib yangilandi"},
        tags=["stages"],
    )
    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        """
        Bosqichlarni drag-drop orqali tartiblash.
        """
        order_list = request.data.get("order", [])
        if not isinstance(order_list, list) or not all(isinstance(i, int) for i in order_list):
            return Response(
                {"detail": "Noto‘g‘ri format. `order` — ID’lar ro‘yxati bo‘lishi kerak."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for idx, stage_id in enumerate(order_list):
                Stage.objects.filter(id=stage_id).update(order=idx + 1)

        return Response({"detail": "Tartib muvaffaqiyatli yangilandi."}, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        method="post",
        operation_summary="Patient bosqichini o'zgartirish",
        operation_description="Bemor bosqichini yangilash",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["patient_id", "stage_id"],
            properties={
                "patient_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Bemor ID"),
                "stage_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Yangi bosqich ID"),
                "comment": openapi.Schema(type=openapi.TYPE_STRING, description="Izoh"),
            },
        ),
        responses={200: "Stage o'zgartirildi"},
        tags=["stages"],
    )
    @action(detail=False, methods=["post"], url_path="change-stage")
    def change_stage(self, request):
        patient_id = request.data.get("patient_id")
        stage_id = request.data.get("stage_id")
        comment = request.data.get("comment", "")

        # ✅ Validate
        if not patient_id or not stage_id:
            return Response(
                {"detail": "patient_id va stage_id kiritilishi shart"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ✅ Patient topish
        try:
            patient = Patient.objects.get(id=patient_id)
        except Patient.DoesNotExist:
            return Response(
                {"detail": "Bunday patient mavjud emas"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ✅ Stage topish
        try:
            stage = Stage.objects.get(id=stage_id)
        except Stage.DoesNotExist:
            return Response(
                {"detail": "Bunday stage mavjud emas"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ✅ Yangilash
        old_stage = patient.stage
        patient.stage = stage
        patient.save()

        # ✅ (Optional) comment bo‘lsa historyga yozish uchun joy
        # StageHistory.objects.create(...)

        return Response(
            {
                "detail": "Stage muvaffaqiyatli o‘zgartirildi",
                "patient_id": patient_id,
                "old_stage": old_stage.id if old_stage else None,
                "new_stage": stage.id,
                "comment": comment,
            },
            status=status.HTTP_200_OK,
        )


# ===============================================================
# 🏷️ TAG VIEWSET
# ===============================================================
class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all().order_by("id")
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "delete"]

    @swagger_auto_schema(
        operation_summary="Barcha teglar ro'yxati",
        operation_description="Barcha mavjud teglarni olish",
        tags=["tags"]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Yangi teg yaratish",
        operation_description="Yangi teg qo'shish",
        tags=["tags"]
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Tegni yangilash",
        operation_description="Tegni to'liq yangilash",
        tags=["tags"]
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Tegni qisman yangilash",
        operation_description="Tegni qisman yangilash",
        tags=["tags"]
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Tegni o'chirish",
        operation_description="Tegni ID bo'yicha o'chirish",
        tags=["tags"]
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
