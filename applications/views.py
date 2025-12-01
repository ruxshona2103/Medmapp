import logging
from django.db import models
from django.shortcuts import get_object_or_404
from rest_framework import generics, viewsets, status, permissions
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import api_view, permission_classes
from django.db.models import Count, Q
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

# --- EXTERNAL IMPORTS (Bemor hujjatlari uchun kerak) ---
from patients.models import Patient, PatientDocument  # ✅ PatientDocument qo'shildi
from patients.serializers import PatientDocumentSerializer  # ✅ Serializer qo'shildi
from core.models import Stage

logger = logging.getLogger(__name__)


# ===============================================================
# PAGINATION - ApplicationViewSet uchun
# ===============================================================
class ApplicationListPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


# ===============================================================
# 🩺 APPLICATIONS VIEWSET - ASOSIY
# ===============================================================
class ApplicationViewSet(viewsets.ModelViewSet):
    """
    🩺 Arizalar bilan ishlovchi asosiy API
    - Bemor o'zi yaratgan arizalarni ko'radi
    - Operator barcha arizalarni boshqaradi
    - Filter: status, sana, klinika, stage, patient_id
    - Pagination: 10 items per page
    """
    queryset = Application.objects.filter(is_archived=False).select_related("patient", "stage")
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  # ✅ File upload uchun
    pagination_class = ApplicationListPagination  # ✅ PAGINATION

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return ApplicationCreateUpdateSerializer
        return ApplicationSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Application.objects.filter(is_archived=False).select_related("patient", "stage")

        # 👤 Faqat bemor o'z arizalarini ko'radi
        if getattr(user, "role", "patient") == "patient" and hasattr(user, "phone_number"):
            try:
                patient = Patient.objects.get(phone_number=user.phone_number)
                qs = qs.filter(patient=patient)
            except Patient.DoesNotExist:
                return Application.objects.none()

        return qs.prefetch_related("documents")

    def get_serializer_context(self):
        """
        Request kontekstni serializer'ga uzatish
        """
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @swagger_auto_schema(
        operation_summary="Arizalar ro'yxati",
        operation_description="Arizalarni filter va pagination bilan olish",
        manual_parameters=[
            openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Qidirish"),
            openapi.Parameter("status", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              enum=["all", "new", "in_progress", "completed", "rejected"], description="Status filter"),
            openapi.Parameter("date", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Sana (YYYY-MM-DD)"),
            openapi.Parameter("patient_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Bemor ID"),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Sahifa"),
            openapi.Parameter("page_size", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Elementlar soni"),
        ],
        responses={200: ApplicationSerializer(many=True)},
        tags=["applications"]
    )
    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()

        # 🔍 Qidiruv
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

        # 📅 Sana filter
        filter_date = request.query_params.get("date")
        if filter_date:
            qs = qs.filter(created_at__date=filter_date)

        # 👤 Patient ID filter
        patient_id = request.query_params.get("patient_id")
        if patient_id:
            qs = qs.filter(patient__id=patient_id)

        # ✅ PAGINATION
        qs = qs.order_by("-created_at")
        page = self.paginate_queryset(qs)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ===============================================================
# 👤 PATIENT ID BO'YICHA ARIZALAR + HUJJATLAR (YANGILANGAN QISM)
# ===============================================================
class ApplicationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class PatientApplicationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    👤 Bemorning barcha arizalarini VA shaxsiy hujjatlarini ko'rish
    - GET /applications/patient/{patient_id}/
    - Response: { "results": [...arizalar], "patient_documents": [...hujjatlar] }
    """
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ApplicationPagination
    lookup_field = 'pk'

    def get_queryset(self):
        patient_id = self.kwargs.get('patient_id')

        if not patient_id:
            return Application.objects.none()

        return Application.objects.filter(
            patient_id=patient_id,
            is_archived=False
        ).select_related('patient', 'stage').prefetch_related('documents').order_by('-created_at')

    def get_serializer_context(self):
        """Context"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @swagger_auto_schema(
        operation_summary="Bemorning arizalari va hujjatlari",
        operation_description="Bemor ID bo'yicha barcha arizalar va uning shaxsiy hujjatlari (pasport va h.k.)",
        manual_parameters=[
            openapi.Parameter('status', openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Status filter"),
            openapi.Parameter('page', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Sahifa"),
            openapi.Parameter('page_size', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Elementlar soni"),
        ],
        responses={200: "Arizalar va Hujjatlar"},
        tags=["patient-applications"]
    )
    def list(self, request, patient_id=None):
        if not patient_id:
            return Response(
                {"detail": "Patient ID topilmadi"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 1. Bemor mavjudligini tekshirish
        if not Patient.objects.filter(id=patient_id).exists():
            return Response(
                {"detail": f"Bemor ID {patient_id} topilmadi"},
                status=status.HTTP_404_NOT_FOUND
            )

        queryset = self.get_queryset()

        # Status filter
        status_filter = request.query_params.get('status')
        if status_filter and status_filter.lower() != 'all':
            queryset = queryset.filter(status=status_filter.lower())

        # ✅ YANGI QISM: Bemorning shaxsiy hujjatlarini (PatientDocument) olish
        # Bu yerda biz Application'ga bog'lanmagan, to'g'ridan-to'g'ri bemor profilidagi hujjatlarni olamiz
        patient_docs = PatientDocument.objects.filter(patient_id=patient_id).order_by('-uploaded_at')
        docs_serializer = PatientDocumentSerializer(patient_docs, many=True, context={'request': request})

        # Pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)

            # 🔥 RESPONSE ICHIGA HUJJATLARNI QO'SHISH
            response.data['patient_documents'] = docs_serializer.data
            return response

        serializer = self.get_serializer(queryset, many=True)

        # Pagination ishlamagan taqdirda ham formatni saqlash
        return Response({
            "results": serializer.data,
            "patient_documents": docs_serializer.data
        })


# ===============================================================
# 📄 DOCUMENT UPLOAD - UploadApplicationDocumentView
# ===============================================================
class UploadApplicationDocumentView(generics.CreateAPIView):
    """
    ✅ Arizaga hujjat yuklash
    """
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        operation_summary="Arizaga hujjat yuklash",
        operation_description="Arizaga fayl biriktirish",
        consumes=["multipart/form-data"],
        manual_parameters=[
            openapi.Parameter("file", openapi.IN_FORM, type=openapi.TYPE_FILE, required=True, description="Fayl"),
            openapi.Parameter("description", openapi.IN_FORM, type=openapi.TYPE_STRING, description="Tavsif")
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

        try:
            ApplicationHistory.objects.create(
                application=application,
                author=request.user,
                comment="Hujjat yuklandi"
            )
        except:
            pass

        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ===============================================================
# 📄 DOCUMENT LIST/CREATE VIEW - DocumentListCreateView
# ===============================================================
class DocumentListCreateView(generics.ListCreateAPIView):
    """
    ✅ Arizaning hujjatlari ro'yxati va yangi hujjat yuklash
    """
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        """Arizaning hujjatlarini olish"""
        application_id = self.kwargs.get('application_id')
        return Document.objects.filter(application_id=application_id).order_by('-uploaded_at')

    @swagger_auto_schema(
        operation_summary="Arizaning hujjatlari ro'yxati",
        tags=["applications"]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Arizaga hujjat yuklash",
        consumes=["multipart/form-data"],
        manual_parameters=[
            openapi.Parameter("file", openapi.IN_FORM, type=openapi.TYPE_FILE, required=True, description="Fayl"),
            openapi.Parameter("description", openapi.IN_FORM, type=openapi.TYPE_STRING, description="Tavsif")
        ],
        responses={201: DocumentSerializer},
        tags=["applications"]
    )
    def post(self, request, *args, **kwargs):
        """Yangi hujjat yuklash"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        application_id = self.kwargs.get('application_id')
        application = get_object_or_404(Application, id=application_id)

        serializer.save(application=application, uploaded_by=request.user)

        try:
            ApplicationHistory.objects.create(
                application=application,
                author=request.user,
                comment="📄 Hujjat yuklandi"
            )
        except:
            pass

        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ===============================================================
# 🔁 BOSQICHNI O'ZGARTIRISH
# ===============================================================
class ChangeApplicationStageView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Bosqichni o'zgartirish",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["new_stage_id"],
            properties={
                "new_stage_id": openapi.Schema(type=openapi.TYPE_INTEGER),
                "comment": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        tags=["applications"],
    )
    def patch(self, request, application_id):
        if getattr(request.user, "role", "") == "patient":
            raise PermissionDenied("Sizda ruxsat yo'q")

        app = get_object_or_404(Application, id=application_id)
        new_stage = get_object_or_404(Stage, id=request.data.get("new_stage_id"))
        old_stage = app.stage
        app.stage = new_stage
        app.save(update_fields=["stage", "updated_at"])

        comment = request.data.get("comment") or f"Bosqich '{old_stage}' → '{new_stage}'"
        try:
            ApplicationHistory.objects.create(
                application=app,
                author=request.user,
                comment=comment
            )
        except:
            pass

        return Response({"success": True, "new_stage": new_stage.title})


# ===============================================================
# ✅ COMPLETED APPLICATIONS - OPERATOR PANELI
# ===============================================================
class CompletedApplicationPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class CompletedApplicationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    🧾 Tugatilgan yoki rad etilgan arizalar
    """
    serializer_class = CompletedApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CompletedApplicationPagination

    def get_queryset(self):
        qs = Application.objects.filter(
            status__in=["completed", "rejected"],
            is_archived=False
        ).select_related("patient", "stage").prefetch_related("documents")

        # 🔍 Qidiruv
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

        # 📅 Sana filter
        filter_date = self.request.query_params.get("date")
        if filter_date:
            qs = qs.filter(created_at__date=filter_date)

        # 👤 Patient ID filter
        patient_id = self.request.query_params.get("patient_id")
        if patient_id:
            qs = qs.filter(patient__id=patient_id)

        return qs.order_by("-created_at")

    @swagger_auto_schema(
        operation_summary="Tugatilgan arizalar",
        manual_parameters=[
            openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Qidirish"),
            openapi.Parameter("status", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              enum=["all", "completed", "rejected"], description="Status"),
            openapi.Parameter("date", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Sana"),
            openapi.Parameter("patient_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Bemor ID"),
        ],
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
        operation_summary="Bitta tugatilgan ariza",
        tags=["applications"],
    )
    def retrieve(self, request, *args, **kwargs):
        app = get_object_or_404(
            Application.objects.select_related("patient", "stage").prefetch_related("documents"),
            id=kwargs.get("pk"),
            status__in=["completed", "rejected"]
        )
        serializer = self.get_serializer(app)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ===============================================================
# 🧾 STATUSNI O'ZGARTIRISH
# ===============================================================
class ChangeApplicationStatusView(generics.UpdateAPIView):
    queryset = Application.objects.all()
    serializer_class = CompletedApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Status o'zgartirish",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["status"],
            properties={
                "status": openapi.Schema(type=openapi.TYPE_STRING, enum=["completed", "rejected"]),
                "final_conclusion": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        tags=["applications"],
    )
    def patch(self, request, *args, **kwargs):
        app_id = kwargs.get("application_id")
        app = get_object_or_404(Application, id=app_id)
        new_status = request.data.get("status")

        if new_status not in ["completed", "rejected"]:
            return Response({"detail": "Noto'g'ri status"}, status=400)

        app.status = new_status
        app.final_conclusion = request.data.get("final_conclusion", "")
        app.updated_at = timezone.now()
        app.save(update_fields=["status", "final_conclusion", "updated_at"])

        try:
            ApplicationHistory.objects.create(
                application=app,
                author=request.user,
                comment=f"Ariza {new_status.upper()} deb belgilandi"
            )
        except:
            pass

        return Response({"success": True, "status": new_status}, status=200)


# ===============================================================
# ✅ STATISTICS API
# ===============================================================
@swagger_auto_schema(
    method='get',
    operation_summary="Arizalar statistikasi",
    responses={200: "Statistika ma'lumotlari"},
    tags=["statistics"]
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def application_statistics(request):
    """
    Arizalar statistikasi
    """
    try:
        stats = Application.objects.aggregate(
            jami=Count('id'),
            yangi=Count('id', filter=Q(status='new')),
            jarayonda=Count('id', filter=Q(status='in_progress')),
            yakunlangan=Count('id', filter=Q(status='completed')),
            rad_etilgan=Count('id', filter=Q(status='rejected')),
        )
        return Response(stats, status=status.HTTP_200_OK)

    except Exception as e:
        import traceback
        print(f"Statistics xatosi: {str(e)}")
        print(traceback.format_exc())

        return Response(
            {'detail': f'Xato: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )