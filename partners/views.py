# partners/views.py
# ===============================================================
# HAMKOR PANEL - VIEWS
# ===============================================================

from rest_framework import viewsets, status, filters, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Count, Prefetch
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

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
# PAGINATION
# ===============================================================
class PartnerPagination(PageNumberPagination):
    """Hamkor panel pagination - 20 per page"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ===============================================================
# PARTNER PATIENT VIEWSET
# ===============================================================
class PartnerPatientViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Hamkor paneli - Bemorlar ViewSet

    ✅ Faqat hamkorga biriktirilgan bemorlar
    ✅ Faqat "HUJJATLAR" va "JAVOB XATLARI" bosqichlaridagi bemorlar
    ✅ Maxfiy ma'lumotlar ko'rinmaydi

    Features:
    - Filter: stage, tag, search
    - Search: full_name
    - Pagination: 20 per page
    """
    permission_classes = [IsAuthenticated, IsPartnerUser]
    pagination_class = PartnerPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter
    ]

    # Filters
    filterset_fields = {
        'stage__code': ['exact'],
        'tag__id': ['exact'],
        'gender': ['exact'],
    }

    # Search
    search_fields = ['full_name']

    # Ordering
    ordering_fields = ['created_at', 'updated_at', 'full_name']
    ordering = ['-updated_at']

    def get_serializer_class(self):
        """Serializer tanlash"""
        if self.action == 'retrieve':
            return PartnerPatientDetailSerializer
        return PartnerPatientListSerializer

    def get_queryset(self):
        """
        Queryset - Faqat hamkorga tegishli bemorlar

        Filters:
        1. assigned_partner = request.user.partner_profile
        2. stage__code in ['stage_documents', 'stage_response']
        3. is_archived = False
        """
        user = self.request.user

        # Partner profilini olish
        try:
            partner = user.partner_profile
        except:
            logger.warning(f"User {user.id} partner profiliga ega emas")
            return Patient.objects.none()

        # Base queryset
        queryset = Patient.objects.filter(
            assigned_partner=partner,
            is_archived=False
        ).select_related(
            'stage', 'tag', 'assigned_partner'
        ).prefetch_related(
            Prefetch('documents', queryset=Patient.documents.through.objects.all()),
            Prefetch('applications', queryset=Patient.applications.through.objects.all()),
            Prefetch('partner_responses', queryset=PartnerResponseDocument.objects.all()),
        ).annotate(
            applications_count=Count('applications')
        )

        # Stage filter - faqat HUJJATLAR va JAVOB_XATLARI
        stage_codes = ['stage_documents', 'stage_response']
        queryset = queryset.filter(stage__code__in=stage_codes)

        # Additional filters from query params
        stage_code = self.request.query_params.get('stage')
        if stage_code:
            queryset = queryset.filter(stage__code=stage_code)

        tag_id = self.request.query_params.get('tag')
        if tag_id:
            queryset = queryset.filter(tag_id=tag_id)

        return queryset

    @swagger_auto_schema(
        operation_summary="📋 Bemorlar ro'yxati - Hamkor paneli",
        operation_description="""
        Hamkorga biriktirilgan bemorlar ro'yxati.

        ✅ Faqat HUJJATLAR va JAVOB_XATLARI bosqichidagi bemorlar
        ✅ Maxfiy ma'lumotlar (pasport, telefon, email) ko'rinmaydi

        Filters:
        - ?stage=stage_documents - Bosqich bo'yicha
        - ?tag=1 - Tag bo'yicha
        - ?search=Aliyev - Ism bo'yicha qidirish
        - ?ordering=-created_at - Saralash
        """,
        manual_parameters=[
            openapi.Parameter('stage', openapi.IN_QUERY, type=openapi.TYPE_STRING, description='Bosqich kodi'),
            openapi.Parameter('tag', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description='Tag ID'),
            openapi.Parameter('search', openapi.IN_QUERY, type=openapi.TYPE_STRING, description='Qidiruv'),
        ],
        responses={200: PartnerPatientListSerializer(many=True)},
        tags=["partner-panel"]
    )
    def list(self, request, *args, **kwargs):
        """Bemorlar ro'yxati"""
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="👤 Bemorning batafsil ma'lumotlari",
        operation_description="""
        Bemorning to'liq ma'lumotlari (maxfiy ma'lumotlarsiz).

        ✅ Ko'rinadi:
        - Ism-Familiya
        - Tibbiy ma'lumotlar (complaints, previous_diagnosis)
        - Hujjatlar
        - Arizalar
        - Hamkor javoblari

        ❌ Ko'rinmaydi:
        - Pasport, telefon, email, tug'ilgan sana, manzil
        """,
        responses={200: PartnerPatientDetailSerializer()},
        tags=["partner-panel"]
    )
    def retrieve(self, request, pk=None):
        """Bemorning batafsil ma'lumotlari"""
        return super().retrieve(request, pk=pk)

    @swagger_auto_schema(
        operation_summary="🔄 Bosqichni o'zgartirish",
        operation_description="""
        Bemorning bosqichini o'zgartirish.

        Masalan: "HUJJATLAR" → "JAVOB XATLARI"

        Tarix:
        - PatientHistory modeliga yoziladi
        - author = current partner user
        """,
        request_body=PartnerStageChangeSerializer,
        responses={200: PartnerPatientDetailSerializer()},
        tags=["partner-panel"]
    )
    @action(detail=True, methods=['patch'], url_path='change-stage')
    def change_stage(self, request, pk=None):
        """
        Bosqichni o'zgartirish

        PATCH /api/v1/partner/patients/{id}/change-stage/

        Body:
        {
          "new_stage": "stage_response",
          "comment": "Tibbiy xulosa tayyorlandi"
        }
        """
        patient = self.get_object()
        serializer = PartnerStageChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_stage_code = serializer.validated_data['new_stage']
        comment = serializer.validated_data.get('comment', '')

        # Stage olish
        try:
            new_stage = Stage.objects.get(code=new_stage_code)
        except Stage.DoesNotExist:
            return Response(
                {"detail": f"Bosqich '{new_stage_code}' topilmadi"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Old stage
        old_stage = patient.stage

        # Yangi stage o'rnatish
        patient.stage = new_stage
        patient.save()

        # Tarixga yozish
        history_comment = comment or f"Bosqich o'zgartirildi: {old_stage.title if old_stage else 'Yoq'} → {new_stage.title}"

        try:
            PatientHistory.objects.create(
                patient=patient,
                author=request.user,
                comment=history_comment
            )
        except Exception as e:
            logger.error(f"PatientHistory xatosi: {e}")

        # Response
        output_serializer = PartnerPatientDetailSerializer(
            patient,
            context={'request': request}
        )
        return Response(output_serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="📤 Javob xati yuklash",
        operation_description="""
        Hamkor tibbiy xulosa, narxlar jadvalini yuklaydi.

        Avtomatik:
        - Bosqich "JAVOB XATLARI"ga o'tadi (agar hali o'tmagan bo'lsa)
        - PartnerResponseDocument yaratiladi
        """,
        consumes=["multipart/form-data"],
        manual_parameters=[
            openapi.Parameter("file", openapi.IN_FORM, type=openapi.TYPE_FILE, required=True),
            openapi.Parameter("title", openapi.IN_FORM, type=openapi.TYPE_STRING),
            openapi.Parameter("description", openapi.IN_FORM, type=openapi.TYPE_STRING),
            openapi.Parameter("document_type", openapi.IN_FORM, type=openapi.TYPE_STRING,
                              enum=['medical_report', 'price_list', 'recommendations', 'other']),
        ],
        responses={201: PartnerResponseDocumentSerializer()},
        tags=["partner-panel"]
    )
    @action(
        detail=True,
        methods=['post'],
        url_path='upload-response',
        parser_classes=[MultiPartParser, FormParser]
    )
    def upload_response(self, request, pk=None):
        """
        Javob xati yuklash

        POST /api/v1/partner/patients/{id}/upload-response/

        Form-data:
        - file: PDF/DOC file
        - title: "Tibbiy xulosa"
        - description: "..."
        - document_type: "medical_report"
        """
        patient = self.get_object()
        partner = request.user.partner_profile

        # Serializer
        serializer = PartnerResponseUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Document yaratish
        document = serializer.save(
            patient=patient,
            partner=partner
        )

        # Bosqichni "JAVOB XATLARI"ga o'tkazish (agar hali o'tmagan bo'lsa)
        response_stage_code = 'stage_response'
        if patient.stage.code != response_stage_code:
            try:
                response_stage = Stage.objects.get(code=response_stage_code)
                old_stage = patient.stage
                patient.stage = response_stage
                patient.save()

                # Tarixga yozish
                PatientHistory.objects.create(
                    patient=patient,
                    author=request.user,
                    comment=f"Javob xati yuklandi. Bosqich: {old_stage.title} → {response_stage.title}"
                )
            except Stage.DoesNotExist:
                logger.error(f"Stage '{response_stage_code}' topilmadi")

        # Response
        output_serializer = PartnerResponseDocumentSerializer(
            document,
            context={'request': request}
        )
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


# ===============================================================
# PARTNER PROFILE VIEW
# ===============================================================
class PartnerProfileView(generics.RetrieveUpdateAPIView):
    """
    Hamkor profili

    GET /api/v1/partner/profile/
    PATCH /api/v1/partner/profile/
    """
    permission_classes = [IsAuthenticated, IsPartnerUser]
    serializer_class = PartnerProfileSerializer

    def get_object(self):
        """Current partner profile"""
        return self.request.user.partner_profile

    @swagger_auto_schema(
        operation_summary="👤 Hamkor profili",
        operation_description="Hamkorning o'z profil ma'lumotlari",
        responses={200: PartnerProfileSerializer()},
        tags=["partner-profile"]
    )
    def get(self, request, *args, **kwargs):
        """Profilni ko'rish"""
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="✏️ Profilni yangilash",
        request_body=PartnerProfileSerializer,
        responses={200: PartnerProfileSerializer()},
        tags=["partner-profile"]
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
        responses={200: PartnerResponseDocumentSerializer(many=True)},
        tags=["partner-responses"]
    )
    def list(self, request, *args, **kwargs):
        """Javob xatlari ro'yxati"""
        return super().list(request, *args, **kwargs)