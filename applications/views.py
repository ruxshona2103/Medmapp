from django.db import models
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone
from django.db.models import Q
from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Application, ApplicationHistory, Document
from .serializers import (
    ApplicationSerializer,
    ApplicationCreateUpdateSerializer, DocumentSerializer, CompletedApplicationSerializer
)
from patients.models import Patient
from core.models import Stage


class ApplicationViewSet(viewsets.ModelViewSet):
    """
    🩺 **Mening Tashxislarim (Arizalar) API**
    - Bemor o‘zi yaratgan arizalarni ko‘radi
    - Operator va admin barcha arizalarni boshqaradi
    - `application_id` (MED-XXXX) yaratishda va javobda chiqadi
    """
    queryset = Application.objects.filter(is_archived=False).select_related("patient", "stage")
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return ApplicationCreateUpdateSerializer
        return ApplicationSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Application.objects.none()

        user = self.request.user
        qs = Application.objects.filter(is_archived=False).select_related("patient", "stage")

        # 👤 Agar bemor bo‘lsa, faqat o‘z arizalarini ko‘radi
        if getattr(user, "role", "patient") == "patient" and hasattr(user, "phone_number"):
            patient = Patient.objects.filter(phone_number=user.phone_number).first()
            if patient:
                qs = qs.filter(patient=patient)

        return qs.prefetch_related("documents", "history")

    # 📋 Arizalar ro‘yxatini olish (filter va search bilan)
    @swagger_auto_schema(
        operation_summary="📋 Arizalar ro‘yxatini olish",
        operation_description="Arizalarni klinika nomi, bemor ID, bosqich yoki holat bo‘yicha filtrlash mumkin.",
        manual_parameters=[
            openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description="Klinika nomi bo‘yicha qidirish (masalan: 'Shifo Clinic')"),
            openapi.Parameter("status", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              enum=["all", "new", "in_progress", "completed", "rejected"],
                              description="Ariza holati bo‘yicha filter (Yangi, Jarayonda, Tugatilgan, Rad etilgan)"),
            openapi.Parameter("stage", openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description="Filtrlash uchun Stage ID (ixtiyoriy)"),
            openapi.Parameter("patient_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description="Bemor ID bo‘yicha filter (operator uchun)")
        ],
        responses={200: ApplicationSerializer(many=True)},
        tags=["Applications"]
    )
    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()

        # 🔍 Qidiruv (clinic_name bo‘yicha)
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(clinic_name__icontains=search)

        # ⚙️ Status filter
        status_filter = request.query_params.get("status")
        if status_filter and status_filter.lower() != "all":
            qs = qs.filter(status=status_filter)

        # 🧩 Stage filter
        stage_id = request.query_params.get("stage")
        if stage_id:
            qs = qs.filter(stage_id=stage_id)

        # 👤 Patient ID filter
        patient_id = request.query_params.get("patient_id")
        if patient_id:
            qs = qs.filter(patient_id=patient_id)

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # 📄 Bitta bemorning barcha arizalarini olish (id orqali)
    @swagger_auto_schema(
        operation_summary="📄 Bitta bemorning barcha arizalarini olish",
        operation_description=(
            "Bitta bemor (ID orqali) yuborgan barcha arizalarni olish. "
            "Status va klinika nomi bo‘yicha filtr ishlaydi. Masalan: "
            "`/applications/applications/5/?status=in_progress&search=Shifo`"
        ),
        manual_parameters=[
            openapi.Parameter("status", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              enum=["all", "new", "in_progress", "completed", "rejected"],
                              description="Ariza holati bo‘yicha filter"),
            openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description="Klinika nomi bo‘yicha qidirish")
        ],
        responses={200: ApplicationSerializer(many=True)},
        tags=["Applications"]
    )
    def retrieve(self, request, *args, **kwargs):
        """🔹 Bitta bemorning barcha arizalarini filter bilan olish"""
        patient_id = kwargs.get("pk")
        patient = get_object_or_404(Patient, id=patient_id)

        qs = Application.objects.filter(patient=patient, is_archived=False).select_related("stage")

        # 🔍 Filtrlar
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(clinic_name__icontains=search)

        status_filter = request.query_params.get("status")
        if status_filter and status_filter.lower() != "all":
            qs = qs.filter(status=status_filter)

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # 🆕 Yangi ariza yaratish
    @swagger_auto_schema(
        operation_summary="🆕 Yangi ariza yaratish",
        operation_description="Bemor yangi ariza yuboradi. Natijada `application_id` (masalan MED-56162) qaytadi.",
        request_body=ApplicationCreateUpdateSerializer,
        responses={201: ApplicationSerializer},
        tags=["Applications"],
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        application = self.perform_create(serializer)
        response_data = ApplicationSerializer(application, context={"request": request}).data
        return Response(response_data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        user = self.request.user
        default_stage = Stage.objects.filter(code_name="yangi").first() or Stage.objects.first()

        if getattr(user, "role", "patient") == "patient":
            patient, _ = Patient.objects.get_or_create(
                created_by=user,
                defaults={
                    "full_name": f"{user.first_name} {user.last_name}".strip(),
                    "phone_number": getattr(user, "phone_number", None)
                }
            )
        else:
            patient = serializer.validated_data.get("patient")

        application = serializer.save(patient=patient, stage=default_stage, status="new")

        ApplicationHistory.objects.create(
            application=application,
            author=user,
            comment="📝 Yangi ariza yaratildi"
        )
        return application

# ===============================================================
# 📎 HUJJATLAR (Document)
# ===============================================================
class DocumentListCreateView(generics.ListCreateAPIView):
    """
    📂 **Ariza hujjatlari**
    - GET → Arizaga biriktirilgan hujjatlar ro‘yxati
    - POST → Yangi hujjat yuklash (PDF, JPG, PNG)
    """
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Document.objects.none()
        application_id = self.kwargs.get("application_id")
        return Document.objects.filter(application__id=application_id)

    @swagger_auto_schema(
        operation_summary="📎 Arizaga hujjat yuklash",
        operation_description="PDF, JPG, PNG formatlarini yuklash uchun API.",
        consumes=["multipart/form-data"],
        manual_parameters=[
            openapi.Parameter(
                name="file",
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=True,
                description="Yuklanadigan fayl (PDF/JPG/PNG)"
            ),
            openapi.Parameter(
                name="description",
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Fayl tavsifi (ixtiyoriy)"
            )
        ],
        responses={201: DocumentSerializer},
        tags=["applications"],
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response([serializer.data], status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        application_id = self.kwargs.get("application_id")
        user = self.request.user
        application = get_object_or_404(Application, id=application_id)
        serializer.save(application=application, uploaded_by=user)
        ApplicationHistory.objects.create(application=application, author=user, comment="📄 Hujjat yuklandi")


# ===============================================================
# 🔁 BOSQICHNI O‘ZGARTIRISH
# ===============================================================
class ChangeApplicationStageView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Swagger uchun himoya
        if getattr(self, 'swagger_fake_view', False):
            return Application.objects.none()
        return Application.objects.all()

    @swagger_auto_schema(
        operation_summary="🔁 Bosqichni o‘zgartirish",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["new_stage_id"],
            properties={
                "new_stage_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Yangi Stage ID"),
                "comment": openapi.Schema(type=openapi.TYPE_STRING, description="Izoh (ixtiyoriy)")
            },
        ),
        responses={200: openapi.Response("Bosqich muvaffaqiyatli o‘zgartirildi")},
        tags=["Applications"],
    )
    def patch(self, request, application_id):
        user = request.user
        if getattr(user, "role", "patient") == "patient":
            raise PermissionDenied("Sizda bosqichni o‘zgartirishga ruxsat yo‘q.")

        application = get_object_or_404(Application, id=application_id)
        new_stage_id = request.data.get("new_stage_id")
        if not new_stage_id:
            return Response({"error": "'new_stage_id' majburiy."}, status=status.HTTP_400_BAD_REQUEST)

        new_stage = get_object_or_404(Stage, id=new_stage_id)
        old_stage = application.stage
        application.stage = new_stage
        application.save(update_fields=["stage", "updated_at"])

        comment = request.data.get("comment") or f"Bosqich '{getattr(old_stage, 'title', '—')}' → '{new_stage.title}' ga o‘zgartirildi"
        ApplicationHistory.objects.create(application=application, author=user, comment=comment)

        return Response([{"success": True, "new_stage": new_stage.title}], status=status.HTTP_200_OK)


# ===============================================================
# ✅ OPERATOR PANELI
# ===============================================================
class CompletedApplicationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    🧾 Bajarilgan yoki rad etilgan murojaatlar API
    """
    serializer_class = CompletedApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Application.objects.none()
        return Application.objects.filter(status__in=["completed", "rejected"], is_archived=False).select_related("patient")

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter("search", openapi.IN_QUERY, description="Bemor yoki klinika bo‘yicha qidirish", type=openapi.TYPE_STRING)
        ],
        tags=["Applications"],
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                models.Q(patient__full_name__icontains=search)
                | models.Q(clinic_name__icontains=search)
            )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


# ===============================================================
# ✅ STATUSNI O‘ZGARTIRISH
# ===============================================================
class ChangeApplicationStatusView(generics.UpdateAPIView):
    queryset = Application.objects.all()
    serializer_class = CompletedApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Application.objects.none()
        return Application.objects.all()

    @swagger_auto_schema(
        operation_summary="🧾 Arizani 'Tugatilgan' yoki 'Rad etilgan' deb belgilash",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["status"],
            properties={
                "status": openapi.Schema(type=openapi.TYPE_STRING, enum=["completed", "rejected"]),
                "final_conclusion": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={200: openapi.Response("Status o‘zgartirildi")},
        tags=["Applications"],
    )
    def patch(self, request, *args, **kwargs):
        app_id = kwargs.get("application_id")
        app = Application.objects.filter(id=app_id).first()
        if not app:
            return Response({"detail": "Ariza topilmadi"}, status=404)

        new_status = request.data.get("status")
        final_conclusion = request.data.get("final_conclusion", "")
        if new_status not in ["completed", "rejected"]:
            return Response({"detail": "Status noto‘g‘ri qiymatga ega"}, status=400)

        app.status = new_status
        app.final_conclusion = final_conclusion
        app.updated_at = timezone.now()
        app.save(update_fields=["status", "final_conclusion", "updated_at"])

        ApplicationHistory.objects.create(
            application=app,
            author=request.user,
            comment=f"Ariza {new_status.upper()} deb belgilandi"
        )
        return Response({"success": True, "status": new_status})
