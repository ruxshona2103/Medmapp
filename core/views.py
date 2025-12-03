from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.db import transaction
from django.db.models import Prefetch, Max

from .models import Stage, Tag
from patients.models import Patient, PatientHistory
from .serializers import StageSerializer, TagSerializer


# ===============================================================
# 🧩 STAGE VIEWSET
# ===============================================================
class StageViewSet(viewsets.ModelViewSet):
    """
    🧩 Bosqichlar (Stage) API
    - Operator stage ni o'zgartirganda, Bemor va uning Arizalari ham o'zgaradi.
    - Agar 'RESPONSES' bosqichiga o'tilsa, avtomatik 'Yangi' tegi beriladi.
    """
    serializer_class = StageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Stage ichidagi bemorlarni optimizatsiya bilan olish
        return Stage.objects.prefetch_related(
            Prefetch("patients", queryset=Patient.objects.all().order_by("-created_at"))
        ).order_by("order", "id")

    def perform_create(self, serializer):
        last_order = Stage.objects.aggregate(max_order=Max("order"))["max_order"] or 0
        serializer.save(order=last_order + 1)

    # --- SWAGGER DOCS ---
    @swagger_auto_schema(tags=["stages"])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(tags=["stages"])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(tags=["stages"])
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(tags=["stages"])
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.id == 1 or instance.code_name == "new":
            return Response(
                {"detail": "‘Yangi’ bosqichni o‘chirib bo‘lmaydi."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Bosqichlarni qayta tartiblash",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "order": openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_INTEGER)),
            },
            required=["order"],
        ),
        tags=["stages"],
    )
    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        order_list = request.data.get("order", [])
        if not isinstance(order_list, list) or not all(isinstance(i, int) for i in order_list):
            return Response({"detail": "Noto‘g‘ri format."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            for idx, stage_id in enumerate(order_list):
                Stage.objects.filter(id=stage_id).update(order=idx + 1)
        return Response({"detail": "Tartib yangilandi."}, status=status.HTTP_200_OK)

    # 👇 ASOSIY LOGIKA (Change Stage + Auto Tag)
    @swagger_auto_schema(
        method="post",
        operation_summary="Patient va uning arizalari bosqichini o'zgartirish",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["patient_id", "stage_id"],
            properties={
                "patient_id": openapi.Schema(type=openapi.TYPE_INTEGER),
                "stage_id": openapi.Schema(type=openapi.TYPE_INTEGER),
                "comment": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        tags=["stages"],
    )
    @action(detail=False, methods=["post"], url_path="change-stage")
    def change_stage(self, request):
        patient_id = request.data.get("patient_id")
        stage_id = request.data.get("stage_id")
        comment = request.data.get("comment", "")

        if not patient_id or not stage_id:
            return Response({"detail": "Ma'lumot yetarli emas"}, status=400)

        try:
            patient = Patient.objects.get(id=patient_id)
            new_stage = Stage.objects.get(id=stage_id)
        except (Patient.DoesNotExist, Stage.DoesNotExist):
            return Response({"detail": "Topilmadi"}, status=404)

        old_stage = patient.stage

        # 🔥 AVTO TAG: "RESPONSES" ga o'tsa -> Tag = "Yangi"
        if new_stage.code_name == 'RESPONSES':
            new_tag, _ = Tag.objects.get_or_create(
                code_name='new',
                defaults={'name': 'Yangi', 'color': '#3B82F6'}
            )
            patient.tag = new_tag
            if not comment:
                comment = "Javob xatlari bosqichiga o'tildi. Status: Yangi"

        # O'zgartirishlar
        with transaction.atomic():
            patient.stage = new_stage
            patient.save()

            # Application sinxronizatsiya
            try:
                from applications.models import Application
                Application.objects.filter(patient=patient, is_archived=False).update(stage=new_stage)
            except Exception:
                pass

            # History
            if comment or old_stage != new_stage:
                try:
                    old_title = old_stage.title if old_stage else "Yo'q"
                    PatientHistory.objects.create(
                        patient=patient,
                        author=request.user,
                        comment=f"Bosqich o'zgartirildi: {old_title} -> {new_stage.title}. {comment}"
                    )
                except:
                    pass

        return Response({
            "success": True,
            "new_stage": new_stage.title,
            "new_tag": patient.tag.name if patient.tag else None
        }, status=200)


# ===============================================================
# 🏷️ TAG VIEWSET (TUZATILDI)
# ===============================================================
class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.prefetch_related('patients').all().order_by("id")

    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "delete"]

    @swagger_auto_schema(tags=["tags"])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(tags=["tags"])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(tags=["tags"])
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(tags=["tags"])
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(tags=["tags"])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)