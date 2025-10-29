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
        """
        Default tartib — `order` qiymati mavjud bo‘lsa, shunga qarab;
        bo‘lmasa, `id` bo‘yicha tartiblaydi.
        """
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
        operation_summary="Barcha bosqichlar ro‘yxati",
        operation_description="Bosqichlar ro‘yxatini `order` yoki `id` bo‘yicha tartiblangan holda qaytaradi.",
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    # ===========================================================
    # ➕ Yangi bosqich yaratish
    # ===========================================================
    @swagger_auto_schema(
        operation_summary="Yangi bosqich yaratish",
        operation_description="Yangi bosqich qo‘shish (faqat operator yoki admin uchun).",
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    # ===========================================================
    # ✏️ Bosqich ma’lumotlarini yangilash
    # ===========================================================
    @swagger_auto_schema(
        operation_summary="Bosqich ma’lumotlarini tahrirlash (PATCH)",
        operation_description="Bosqich nomi, rangi yoki boshqa atributlarini qisman yangilash imkonini beradi.",
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    # ===========================================================
    # 🗑️ Bosqichni o‘chirish
    # ===========================================================
    @swagger_auto_schema(
        operation_summary="Bosqichni o‘chirish",
        operation_description="Faqat operator yoki admin foydalanuvchi o‘chira oladi. ‘Yangi’ bosqichni o‘chirib bo‘lmaydi.",
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
        operation_description=(
            "Frontenddagi drag-drop orqali yuborilgan tartib asosida `order` qiymatlarini yangilaydi.\n\n"
            "**Body misol:**\n"
            "```\n"
            "{ \"order\": [3, 1, 5, 2] }\n"
            "```\n"
            "Bu holatda 3-id birinchi, 1-id ikkinchi, 5-id uchinchi bo‘lib tartiblanadi."
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "order": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_INTEGER),
                    description="Bosqich ID’lari yangi tartibda"
                ),
            },
            required=["order"],
        ),
        responses={200: "Tartib muvaffaqiyatli yangilandi"},
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

class TagViewSet(viewsets.ModelViewSet):
    """
    TZ 3.2: Teglar (Tag) API
    - Operator yoki admin foydalanuvchilar uchun CRUD
    - GET /tags/ — barcha teglar ro‘yxati
    - POST /tags/ — yangi teg yaratish
    - PUT/PATCH /tags/{id}/ — tegni yangilash
    - DELETE /tags/{id}/ — tegni o‘chirish
    """
    queryset = Tag.objects.all().order_by("id")
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "delete"]

    @swagger_auto_schema(operation_description="Barcha teglar ro‘yxatini olish.")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(operation_description="Yangi teg yaratish (faqat operator yoki admin uchun).")
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(operation_description="Tegni to‘liq yangilash (PUT).")
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(operation_description="Tegni qisman yangilash (PATCH).")
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(operation_description="Tegni o‘chirish (ID bo‘yicha).")
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
