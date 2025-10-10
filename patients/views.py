from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from core.models import Stage
from .models import Patient, PatientHistory, PatientDocument, Contract
from .serializers import (
    PatientListSerializer,
    PatientDetailSerializer,
    PatientCreateUpdateSerializer,
    PatientDocumentSerializer,
    PatientProfileSerializer,
)
from .utils import get_default_stage


# ===============================================================
# 🧩 3.1 — BEMORLAR CRUD
# ===============================================================
class PatientViewSet(viewsets.ModelViewSet):
    """
    Bemorlar (TZ 3.1):
    - GET /patients/ — Kanban uchun ro'yxat (search, stage_id, tag_id, page, per_page)
    - POST /patients/ — Yangi bemor yaratish (tarixga "Bemor profili yaratildi")
    - GET /patients/{id}/ — Bemorning to'liq ma'lumotlari (tarix, hujjatlar bilan)
    - PUT /patients/{id}/ — Ma'lumotlarni tahrirlash (har bir o'zgarish tarixga yoziladi)
    - DELETE /patients/{id}/ — Soft delete (arxivlash)
    """
    permission_classes = [IsAuthenticated]
    queryset = Patient.objects.filter(is_archived=False).select_related("stage", "tag").order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "list":
            return PatientListSerializer
        if self.action == "retrieve":
            return PatientDetailSerializer
        return PatientCreateUpdateSerializer

    @swagger_auto_schema(
        operation_description="Barcha bemorlar ro'yxati (Kanban). Filtrlar: search, stage_id, tag_id, page, per_page.",
        manual_parameters=[
            openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Ism/telefon/email bo‘yicha qidirish"),
            openapi.Parameter("stage_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Bosqich ID"),
            openapi.Parameter("tag_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Teg ID"),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Sahifa"),
            openapi.Parameter("per_page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Sahifadagi elementlar soni"),
        ],
        responses={200: PatientListSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        search = request.query_params.get("search")
        stage_id = request.query_params.get("stage_id")
        tag_id = request.query_params.get("tag_id")

        if search:
            qs = qs.filter(
                Q(full_name__icontains=search) |
                Q(phone_number__icontains=search) |
                Q(email__icontains=search)
            )
        if stage_id:
            qs = qs.filter(stage_id=stage_id)
        if tag_id:
            qs = qs.filter(tag_id=tag_id)

        # Simple pagination
        page = int(request.query_params.get("page", 1))
        per_page = int(request.query_params.get("per_page", 20))
        start = (page - 1) * per_page
        end = start + per_page

        serializer = PatientListSerializer(qs[start:end], many=True, context={"request": request})
        return Response({
            "count": qs.count(),
            "page": page,
            "per_page": per_page,
            "results": serializer.data
        })

    @swagger_auto_schema(
        operation_description="Yangi bemor yaratish. Tarixga 'Bemor profili yaratildi' yoziladi. Stage/tag kelmasa — default qo‘yiladi.",
        request_body=PatientCreateUpdateSerializer,
        responses={201: PatientDetailSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = PatientCreateUpdateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        payload = {**serializer.validated_data}

        if not payload.get("stage"):
            payload["stage"] = get_default_stage()

        patient = Patient.objects.create(created_by=request.user, **payload)
        PatientHistory.objects.create(patient=patient, author=request.user, comment="Bemor profili yaratildi")

        return Response(
            PatientDetailSerializer(patient, context={"request": request}).data,
            status=status.HTTP_201_CREATED
        )

    @swagger_auto_schema(
        operation_description="Bitta bemorning to‘liq ma'lumotlari (tarix va hujjatlar bilan).",
        responses={200: PatientDetailSerializer},
    )
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return Response(PatientDetailSerializer(instance, context={"request": request}).data)

    @swagger_auto_schema(
        operation_description="Bemor ma'lumotlarini yangilash. Har bir o‘zgarish PatientHistoryga yoziladi.",
        request_body=PatientCreateUpdateSerializer,
        responses={200: PatientDetailSerializer},
    )
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = PatientCreateUpdateSerializer(instance, data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        patient = serializer.save()
        PatientHistory.objects.create(patient=patient, author=request.user, comment="Bemor ma'lumotlari yangilandi")
        return Response(PatientDetailSerializer(patient, context={"request": request}).data)

    @swagger_auto_schema(operation_description="Bemorni arxivlash (soft delete).")
    def destroy(self, request, *args, **kwargs):
        patient = self.get_object()
        patient.is_archived = True
        patient.archived_at = timezone.now()
        patient.save(update_fields=["is_archived", "archived_at"])
        PatientHistory.objects.create(patient=patient, author=request.user, comment="Bemor arxivlandi (soft delete)")
        return Response(status=status.HTTP_204_NO_CONTENT)

    @swagger_auto_schema(
        method="patch",
        operation_description="Bemorning bosqichini o‘zgartirish.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["new_stage_id"],
            properties={
                "new_stage_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Yangi bosqich IDsi"),
                "comment": openapi.Schema(type=openapi.TYPE_STRING, description="Izoh (ixtiyoriy)"),
            },
        ),
        responses={200: openapi.Response("success: true")},
    )
    @action(detail=True, methods=["patch"], url_path="change-stage")
    def change_stage(self, request, pk=None):
        patient = self.get_object()
        new_stage_id = request.data.get("new_stage_id")
        comment = request.data.get("comment", "")
        stage = get_object_or_404(Stage, pk=new_stage_id)
        patient.stage = stage
        patient.save(update_fields=["stage", "updated_at"])
        PatientHistory.objects.create(
            patient=patient,
            author=request.user,
            comment=comment or f"Bosqich '{stage.title}' ga o‘zgartirildi",
        )
        return Response({"success": True})


# ===============================================================
# 🧩 3.4 — HUJJATLAR
# ===============================================================
class PatientDocumentViewSet(mixins.CreateModelMixin,
                             mixins.DestroyModelMixin,
                             viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = PatientDocument.objects.all()
    serializer_class = PatientDocumentSerializer
    parser_classes = (MultiPartParser, FormParser)

    @swagger_auto_schema(
        operation_summary="Muayyan bemorga yangi hujjat yuklash",
        manual_parameters=[
            openapi.Parameter("patient_pk", openapi.IN_PATH, description="Bemor ID raqami", type=openapi.TYPE_INTEGER, required=True),
            openapi.Parameter("file", openapi.IN_FORM, type=openapi.TYPE_FILE, description="Fayl yuklash (PDF, JPG, PNG va h.k.)", required=True),
            openapi.Parameter("description", openapi.IN_FORM, type=openapi.TYPE_STRING, description="Fayl tavsifi (ixtiyoriy)"),
            openapi.Parameter("source_type", openapi.IN_FORM, type=openapi.TYPE_STRING,
                              enum=["operator", "patient", "partner"],
                              description="Kim tomonidan yuklandi", required=True),
        ],
        responses={201: PatientDocumentSerializer}
    )
    def create(self, request, *args, **kwargs):
        patient_pk = kwargs.get("patient_pk")
        patient = get_object_or_404(Patient, pk=patient_pk)
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        document = serializer.save(patient=patient, uploaded_by=request.user)
        PatientHistory.objects.create(patient=patient, author=request.user,
                                      comment=f"Hujjat yuklandi: {serializer.validated_data.get('description', '')}")
        return Response(self.get_serializer(document, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(operation_description="Hujjatni o‘chirish.", responses={204: "Deleted successfully"})
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        patient = instance.patient
        PatientHistory.objects.create(patient=patient, author=request.user,
                                      comment=f"Hujjat o‘chirildi: {instance.description or instance.file.name}")
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ===============================================================
# 🧩 3.5 — JAVOB XATLARI
# ===============================================================
class ResponseLettersViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(operation_description="response_letters bosqichidagi bemorlar va 'partner' hujjatlari.")
    def list(self, request):
        stage = Stage.objects.filter(code_name="response_letters").first()
        if not stage:
            return Response([], status=200)
        patients = Patient.objects.filter(stage=stage, is_archived=False).order_by("-created_at")
        data = []
        for p in patients:
            partner_docs = p.documents.filter(source_type="partner")
            data.append({
                "patient": PatientListSerializer(p, context={"request": request}).data,
                "partner_documents": PatientDocumentSerializer(partner_docs, many=True, context={"request": request}).data
            })
        return Response(data)


# ===============================================================
# 🧩 5.1 — SHARTNOMANI TASDIQLASH
# ===============================================================
class ContractApproveViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        method="post",
        operation_description="Bemor shartnomani tasdiqlaydi (status=approved).",
    )
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        contract = get_object_or_404(Contract, pk=pk)
        contract.status = "approved"
        contract.approved_at = timezone.now()
        contract.save(update_fields=["status", "approved_at"])
        return Response({"status": "approved"})


# ===============================================================
# 🧩 5.2 — BEMOR PROFILI
# ===============================================================
class MeProfileView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(operation_description="Joriy user uchun Patient profili (bemorga mo‘ljallangan panel).")
    def get(self, request):
        patient = Patient.objects.filter(created_by=request.user, is_archived=False).order_by("-created_at").first()
        if not patient:
            return Response({"detail": "Patient topilmadi"}, status=404)
        return Response(PatientProfileSerializer(patient).data)
