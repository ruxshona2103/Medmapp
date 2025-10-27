# ===============================================================
# HAMKOR PANEL - VIEWS (code_name bilan, FINAL)
# ===============================================================

from rest_framework import viewsets, status, filters, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema

from .models import Partner, PartnerResponseDocument
from .serializers import (
    PartnerPatientListSerializer,
    PartnerPatientDetailSerializer,
    PartnerStageChangeSerializer,
    PartnerResponseUploadSerializer,
    PartnerResponseDocumentSerializer,
    PartnerProfileSerializer,
)
from .permissions import IsPartnerUser
from patients.models import Patient, PatientHistory
from core.models import Stage

import logging

logger = logging.getLogger(__name__)

# ===============================================================
# HAMKOR PANEL - VIEWS (code_name bilan, FINAL)
# ===============================================================

from rest_framework import viewsets, status, filters, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import PartnerResponseDocument
from .serializers import (
    PartnerPatientListSerializer,
    PartnerPatientDetailSerializer,
    PartnerResponseUploadSerializer,
    PartnerResponseDocumentSerializer,
    PartnerProfileSerializer,
)
from .permissions import IsPartnerUser
from patients.models import Patient, PatientHistory
from core.models import Stage

import logging

logger = logging.getLogger(__name__)


# ===============================================================
# PAGINATION
# ===============================================================
class PartnerPagination(PageNumberPagination):
    """Hamkor panel pagination"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ===============================================================
# PARTNER PATIENT VIEWSET
# ===============================================================
class PartnerPatientViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Hamkor paneli - Bemorlar
    - Faqat HUJJATLAR va JAVOB_XATLARI bosqichidagi bemorlar
    - Faqat hamkorga biriktirilgan bemorlar
    - Maxfiy ma'lumotlar ko'rinmaydi
    """

    permission_classes = [IsAuthenticated, IsPartnerUser]
    pagination_class = PartnerPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    filterset_fields = {
        'stage__id': ['exact'],
        'tag__id': ['exact'],
        'gender': ['exact'],
    }
    search_fields = ['full_name']
    ordering_fields = ['created_at', 'updated_at', 'full_name']
    ordering = ['-updated_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PartnerPatientDetailSerializer
        return PartnerPatientListSerializer

    def get_queryset(self):
        """✅ Faqat hamkorga tegishli bemorlarni qaytaradi"""
        user = self.request.user

        try:
            partner = user.partner_profile
        except Exception:
            logger.warning(f"User {user.id} partner profiliga ega emas")
            return Patient.objects.none()

        queryset = Patient.objects.filter(
            assigned_partner=partner,
            is_archived=False
        ).select_related(
            'stage', 'tag', 'assigned_partner'
        ).prefetch_related(
            'documents',
            'partner_responses',
        )

        try:
            active_stage_ids = Stage.objects.filter(
                code_name__in=['DOCUMENTS', 'RESPONSE']
            ).values_list('id', flat=True)
            queryset = queryset.filter(stage_id__in=active_stage_ids)
        except Exception as e:
            logger.error(f"Stage filter xatosi: {e}")

        return queryset

    @swagger_auto_schema(
        operation_summary="📤 Javob xati yuklash",
        operation_description="""
            Hamkor tibbiy xulosa, narxlar jadvalini yuklaydi.

            Avtomatik:
            - Bosqich "JAVOB XATLARI"ga o'tadi (agar hali o'tmagan bo'lsa)
            - PartnerResponseDocument yaratiladi
            """,
        manual_parameters=[
            openapi.Parameter(
                'full_name', openapi.IN_FORM,
                description="Bemor to‘liq ismi",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'gender', openapi.IN_FORM,
                description="Jinsi (Erkak / Ayol)",
                type=openapi.TYPE_STRING,
                enum=["Erkak", "Ayol"],
                required=True
            ),
            openapi.Parameter(
                'file', openapi.IN_FORM,
                description="Fayl yuklash (PDF/PNG/DOCX)",
                type=openapi.TYPE_FILE,
                required=True
            ),
            openapi.Parameter(
                'title', openapi.IN_FORM,
                description="Fayl nomi yoki sarlavhasi",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'description', openapi.IN_FORM,
                description="Qo‘shimcha izoh (ixtiyoriy)",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'document_type', openapi.IN_FORM,
                description="Hujjat turi",
                type=openapi.TYPE_STRING,
                enum=["medical_report", "price_list", "recommendations", "other"],
                required=False
            ),
            openapi.Parameter(
                'id', openapi.IN_PATH,
                description="Bemor ID",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
        ],
        responses={201: PartnerResponseDocumentSerializer()},
        tags=['partner'],
    )
    @action(
        detail=True,
        methods=['post'],
        url_path='upload-response',
        parser_classes=[MultiPartParser, FormParser]
    )
    def upload_response(self, request, pk=None):
        """📤 Javob xati yuklash (file bilan birga)"""
        patient = self.get_object()
        partner = request.user.partner_profile

        serializer = PartnerResponseUploadSerializer(
            data=request.data,
            context={'request': request, 'patient': patient, 'partner': partner}
        )
        serializer.is_valid(raise_exception=True)
        document = serializer.save()

        # ===============================================================
        # ✅ Bosqichni RESPONSE ga o‘tkazish
        # ===============================================================
        response_stage, _ = Stage.objects.get_or_create(
            code_name='RESPONSE',
            defaults={'title': 'Javob xatlari'}
        )

        if not patient.stage or patient.stage.code_name != 'RESPONSE':
            old_stage = patient.stage
            patient.stage = response_stage
            patient.save(update_fields=['stage', 'updated_at'])

            try:
                PatientHistory.objects.create(
                    patient=patient,
                    author=request.user,
                    comment=f"📄 Javob xati yuklandi. Bosqich: {old_stage.title if old_stage else 'Yangi'} → {response_stage.title}"
                )
            except Exception as e:
                logger.error(f"PatientHistory yozishda xato: {e}")

        # ✅ Natija
        output_serializer = PartnerResponseDocumentSerializer(
            document, context={'request': request}
        )
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

# ===============================================================
# PARTNER PROFILE VIEW
# ===============================================================
class PartnerProfileView(generics.RetrieveUpdateAPIView):
    """
    Hamkor profili

    GET  /api/v1/partner/profile/
    PATCH /api/v1/partner/profile/
    """

    permission_classes = [IsAuthenticated, IsPartnerUser]
    serializer_class = PartnerProfileSerializer

    def get_object(self):
        """Current partner profile"""
        return self.request.user.partner_profile

    @swagger_auto_schema(
        operation_summary="👤 Hamkor profili",
        tags=['partner']
    )
    def get(self, request, *args, **kwargs):
        """Profilni ko'rish"""
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="✏️ Profilni yangilash",
        tags=['partner']
    )
    def patch(self, request, *args, **kwargs):
        """Profilni yangilash"""
        return super().patch(request, *args, **kwargs)


# ===============================================================
# PARTNER RESPONSE DOCUMENTS VIEWSET
# ===============================================================
class PartnerResponseDocumentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Hamkor javob xatlari ro'yxati

    GET /api/v1/partner/responses/
    GET /api/v1/partner/responses/{id}/
    """

    permission_classes = [IsAuthenticated, IsPartnerUser]
    serializer_class = PartnerResponseDocumentSerializer
    pagination_class = PartnerPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['document_type', 'patient_id']
    ordering_fields = ['uploaded_at']
    ordering = ['-uploaded_at']

    def get_queryset(self):
        """Faqat hamkorning javoblari"""
        partner = self.request.user.partner_profile
        return PartnerResponseDocument.objects.filter(
            partner=partner
        ).select_related('patient', 'partner')

    @swagger_auto_schema(
        operation_summary="📄 Javob xatlari ro'yxati",
        tags=['partner']
    )
    def list(self, request, *args, **kwargs):
        """Javob xatlari ro'yxati"""
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="📄 Javob xati detail",
        tags=['partner']
    )
    def retrieve(self, request, pk=None):
        """Javob xati detail"""
        return super().retrieve(request, pk=pk)
