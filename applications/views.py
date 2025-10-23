from django.db import models
from django.shortcuts import get_object_or_404
from rest_framework import generics, viewsets, status, permissions
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Application, ApplicationHistory, Document
from .serializers import (
    ApplicationSerializer,
    ApplicationCreateUpdateSerializer,
    DocumentSerializer,
    CompletedApplicationSerializer,
)
from patients.models import Patient
from core.models import Stage


# ===============================================================
# 🩺 APPLICATIONS – Yangi va jarayondagi murojaatlar
# ===============================================================
class ApplicationViewSet(viewsets.ModelViewSet):
    """
    🩺 Arizalar bilan ishlovchi asosiy API
    - Bemor o'zi yaratgan arizalarni ko'radi
    - Operator barcha arizalarni boshqaradi
    - Filter: status, sana (bitta), klinika nomi, stage, patient_id
    """
    queryset = Application.objects.filter(is_archived=False).select_related("patient", "stage")
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return ApplicationCreateUpdateSerializer
        return ApplicationSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Application.objects.filter(is_archived=False).select_related("patient", "stage")

        # 👤 Faqat bemor o'z arizalarini ko'radi
        if getattr(user, "role", "patient") == "patient" and hasattr(user, "phone_number"):
            patient = Patient.objects.filter(phone_number=user.phone_number).first()
            if patient:
                qs = qs.filter(patient=patient)

        return qs.prefetch_related("documents", "history")

    # 📋 Arizalar ro'yxatini olish
    @swagger_auto_schema(
        operation_summary="📋 Arizalar ro'yxatini olish (status va sana bo'yicha filter bilan)",
        operation_description=(
                "Arizalarni holati yoki sana bo'yicha filtrlash mumkin. "
                "`status` (new, in_progress, completed, rejected), "
                "`date` formati: YYYY-MM-DD, "
                "`patient_id` bemor ID bo'yicha filter"
        ),
        manual_parameters=[
            openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description="Klinika yoki bemor nomi bo'yicha qidirish"),
            openapi.Parameter("status", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              enum=["all", "new", "in_progress", "completed", "rejected"],
                              description="Ariza holati bo'yicha filter"),
            openapi.Parameter("date", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description="Aynan shu sanada yaratilgan murojaatlar (YYYY-MM-DD)"),
            openapi.Parameter("patient_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description="Bemor ID bo'yicha filter"),
        ],
        responses={200: ApplicationSerializer(many=True)},
        tags=["applications"]
    )
    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()

        # 🔍 Qidiruv (bemor yoki klinika bo'yicha)
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(
                models.Q(clinic_name__icontains=search)
                | models.Q(patient__full_name__icontains=search)
            )

        # ⚙️ Status filter
        status_filter = request.query_params.get("status")
        if status_filter and status_filter.lower() != "all":
            qs = qs.filter(status=status_filter.lower())

        # 📅 Bitta sana bo'yicha filter
        filter_date = request.query_params.get("date")
        if filter_date:
            qs = qs.filter(created_at__date=filter_date)

        # 👤 Patient ID bo'yicha filter
        patient_id = request.query_params.get("patient_id")
        if patient_id:
            qs = qs.filter(patient__id=patient_id)

        serializer = self.get_serializer(qs.order_by("-created_at"), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ===============================================================
# 👤 PATIENT ID BO'YICHA ARIZALAR
# ===============================================================
class ApplicationPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class PatientApplicationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    👤 Bemorning barcha arizalarini ko'rish (patient_id bo'yicha)
    - GET /applications/patient/{patient_id}/ - Bemorning barcha arizalari
    - Filter: status, search (clinic), date
    - Pagination qo'llab-quvvatlanadi
    """
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ApplicationPagination
    lookup_field = 'patient_id'

    def get_queryset(self):
        patient_id = self.kwargs.get('patient_id')
        qs = Application.objects.filter(
            patient__id=patient_id,
            is_archived=False
        ).select_related("patient", "stage").prefetch_related("documents", "history")

        # 🔍 Qidiruv (klinika nomi bo'yicha)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(clinic_name__icontains=search)

        # ⚙️ Status filter
        status_filter = self.request.query_params.get("status")
        if status_filter and status_filter.lower() != "all":
            qs = qs.filter(status=status_filter.lower())

        # 📅 Sana bo'yicha filter
        filter_date = self.request.query_params.get("date")
        if filter_date:
            qs = qs.filter(created_at__date=filter_date)

        return qs.order_by("-created_at")

    @swagger_auto_schema(
        operation_summary="👤 Bemorning barcha arizalarini olish",
        operation_description="Bemor ID bo'yicha barcha arizalarni ko'rish. Search (clinic), status, date filterlari bilan. Paginatsiya qo'llab-quvvatlanadi.",
        manual_parameters=[
            openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description="Klinika nomi bo'yicha qidirish"),
            openapi.Parameter("status", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              enum=["all", "new", "in_progress", "completed", "rejected"],
                              description="Ariza holati bo'yicha filter"),
            openapi.Parameter("date", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description="Sana bo'yicha filter (YYYY-MM-DD)"),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description="Sahifa raqami"),
            openapi.Parameter("page_size", openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description="Sahifadagi elementlar soni (max 100)"),
        ],
        responses={200: ApplicationSerializer(many=True)},
        tags=["applications"]
    )
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        # Pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="👤 Bemorning bitta arizasini olish (application_id bo'yicha)",
        operation_description="Bemor ID va Application ID bo'yicha bitta arizaning to'liq ma'lumotlarini olish",
        responses={200: ApplicationSerializer()},
        tags=["applications"]
    )
    def retrieve(self, request, *args, **kwargs):
        patient_id = self.kwargs.get('patient_id')
        app_id = self.kwargs.get('pk')

        app = get_object_or_404(
            Application.objects.select_related("patient", "stage").prefetch_related("documents", "history"),
            id=app_id,
            patient__id=patient_id,
            is_archived=False
        )
        serializer = self.get_serializer(app)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ===============================================================
# 📎 HUJJATLAR (Documents)
# ===============================================================
class DocumentListCreateView(generics.ListCreateAPIView):
    """
    📂 Arizaga biriktirilgan hujjatlar bilan ishlaydi
    - GET → Hujjatlar ro'yxatini olish
    - POST → Fayl yuklash (PDF, JPG, PNG)
    """
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        app_id = self.kwargs.get("application_id")
        return Document.objects.filter(application__id=app_id)

    @swagger_auto_schema(
        operation_summary="📎 Arizaga hujjat yuklash",
        operation_description="PDF, JPG, PNG formatlarini yuklash uchun API.",
        consumes=["multipart/form-data"],
        manual_parameters=[
            openapi.Parameter("file", openapi.IN_FORM, type=openapi.TYPE_FILE, required=True,
                              description="Yuklanadigan fayl (PDF/JPG/PNG)"),
            openapi.Parameter("description", openapi.IN_FORM, type=openapi.TYPE_STRING,
                              description="Fayl tavsifi (ixtiyoriy)")
        ],
        responses={201: DocumentSerializer},
        tags=["applications"],
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        app_id = self.kwargs.get("application_id")
        application = get_object_or_404(Application, id=app_id)
        serializer.save(application=application, uploaded_by=request.user)
        ApplicationHistory.objects.create(application=application, author=request.user, comment="📄 Hujjat yuklandi")
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ===============================================================
# 🔁 BOSQICHNI O'ZGARTIRISH
# ===============================================================
class ChangeApplicationStageView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="🔁 Bosqichni o'zgartirish",
        operation_description="Yangi Stage ID va izoh yuboriladi.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["new_stage_id"],
            properties={
                "new_stage_id": openapi.Schema(type=openapi.TYPE_INTEGER),
                "comment": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={200: openapi.Response("Bosqich muvaffaqiyatli o'zgartirildi")},
        tags=["applications"],
    )
    def patch(self, request, application_id):
        if getattr(request.user, "role", "") == "patient":
            raise PermissionDenied("Sizda bosqichni o'zgartirishga ruxsat yo'q.")
        app = get_object_or_404(Application, id=application_id)
        new_stage = get_object_or_404(Stage, id=request.data.get("new_stage_id"))
        old_stage = app.stage
        app.stage = new_stage
        app.save(update_fields=["stage", "updated_at"])
        comment = request.data.get("comment") or f"Bosqich '{old_stage}' → '{new_stage}' ga o'zgartirildi"
        ApplicationHistory.objects.create(application=app, author=request.user, comment=comment)
        return Response({"success": True, "new_stage": new_stage.title})


# ===============================================================
# ✅ OPERATOR PANELI – BAJARILGAN MUROJAATLAR
# ===============================================================
class CompletedApplicationPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class CompletedApplicationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    🧾 Tugatilgan yoki rad etilgan murojaatlar (Operator uchun)
    """
    serializer_class = CompletedApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CompletedApplicationPagination

    def get_queryset(self):
        qs = Application.objects.filter(
            status__in=["completed", "rejected"],
            is_archived=False
        ).select_related("patient", "stage").prefetch_related("documents", "history")

        # 🔍 Qidiruv (bemor yoki klinika)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                models.Q(patient__full_name__icontains=search)
                | models.Q(clinic_name__icontains=search)
            )

        # ⚙️ Status filter
        status_filter = self.request.query_params.get("status")
        if status_filter and status_filter.lower() != "all":
            qs = qs.filter(status=status_filter.lower())

        # 📅 Sana bo'yicha filter
        filter_date = self.request.query_params.get("date")
        if filter_date:
            qs = qs.filter(created_at__date=filter_date)

        # 👤 Patient ID bo'yicha filter
        patient_id = self.request.query_params.get("patient_id")
        if patient_id:
            qs = qs.filter(patient__id=patient_id)

        return qs.order_by("-created_at")

    @swagger_auto_schema(
        operation_summary="🧾 Tugatilgan yoki rad etilgan murojaatlar ro'yxati",
        operation_description="Operator paneli uchun tugatilgan va rad etilgan murojaatlar (search, status, date, patient_id filter bilan). Paginatsiya qo'llab-quvvatlanadi.",
        manual_parameters=[
            openapi.Parameter("search", openapi.IN_QUERY, description="Bemor yoki klinika bo'yicha qidirish",
                              type=openapi.TYPE_STRING),
            openapi.Parameter("status", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              enum=["all", "completed", "rejected"], description="Status bo'yicha filter"),
            openapi.Parameter("date", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description="Sana bo'yicha filter (YYYY-MM-DD)"),
            openapi.Parameter("patient_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description="Bemor ID bo'yicha filter"),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description="Sahifa raqami"),
            openapi.Parameter("page_size", openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description="Sahifadagi elementlar soni (max 100)"),
        ],
        responses={200: CompletedApplicationSerializer(many=True)},
        tags=["applications"],
    )
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="📄 Bitta tugatilgan yoki rad etilgan murojaat (id orqali)",
        operation_description="Tugatilgan yoki rad etilgan murojaat tafsilotlarini olish uchun ishlatiladi.",
        responses={200: CompletedApplicationSerializer()},
        tags=["applications"],
    )
    def retrieve(self, request, *args, **kwargs):
        app = get_object_or_404(
            Application.objects.select_related("patient", "stage").prefetch_related("documents", "history"),
            id=kwargs.get("pk"),
            status__in=["completed", "rejected"]
        )
        serializer = self.get_serializer(app)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ===============================================================
# 🧾 STATUSNI O'ZGARTIRISH (Tugatish / Rad etish)
# ===============================================================
class ChangeApplicationStatusView(generics.UpdateAPIView):
    queryset = Application.objects.all()
    serializer_class = CompletedApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

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
        responses={200: openapi.Response("Status o'zgartirildi")},
        tags=["applications"],
    )
    def patch(self, request, *args, **kwargs):
        app_id = kwargs.get("application_id")
        app = get_object_or_404(Application, id=app_id)
        new_status = request.data.get("status")
        if new_status not in ["completed", "rejected"]:
            return Response({"detail": "Noto'g'ri status qiymati"}, status=400)

        app.status = new_status
        app.final_conclusion = request.data.get("final_conclusion", "")
        app.updated_at = timezone.now()
        app.save(update_fields=["status", "final_conclusion", "updated_at"])
        ApplicationHistory.objects.create(application=app, author=request.user,
                                          comment=f"Ariza {new_status.upper()} deb belgilandi")
        return Response({"success": True, "status": new_status}, status=200)