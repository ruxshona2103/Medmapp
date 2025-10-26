# partners/views.py
# ===============================================================
# HAMKOR PANEL - VIEWS (code_name bilan, FINAL)
# ===============================================================

from rest_framework import viewsets, status, filters, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.pagination import PageNumberPagination
from django.db.models import Count
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

    TZ bo'yicha:
    - Faqat HUJJATLAR va JAVOB_XATLARI bosqichidagi bemorlar
    - Faqat hamkorga biriktirilgan bemorlar
    - Maxfiy ma'lumotlar ko'rinmaydi
    """

    permission_classes = [IsAuthenticated, IsPartnerUser]
    pagination_class = PartnerPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    # Filters
    filterset_fields = {
        'stage__id': ['exact'],
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

        ✅ code_name ishlatish (migration kerak emas!)
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
            'documents',
            'partner_responses',
        )

        # ===============================================================
        # ✅ STAGE FILTER (code_name ishlatish)
        # ===============================================================
        try:
            # TZ: HUJJATLAR va JAVOB_XATLARI
            stage_code_names = ['DOCUMENTS', 'RESPONSE']

            # Stage ID larini olish
            active_stage_ids = Stage.objects.filter(
                code_name__in=stage_code_names
            ).values_list('id', flat=True)

            # Bemorlarni filter qilish
            queryset = queryset.filter(stage_id__in=active_stage_ids)

        except Exception as e:
            logger.error(f"Stage filter xatosi: {e}")
            # Agar xato bo'lsa, hamma bemorlarni qaytarish
            pass

        return queryset

    @swagger_auto_schema(
        operation_summary="📋 Bemorlar ro'yxati",
        operation_description="""
        Hamkorga biriktirilgan bemorlar ro'yxati.

        **TZ talablari:**
        - ✅ Faqat HUJJATLAR va JAVOB_XATLARI bosqichidagi bemorlar
        - ✅ Faqat hamkorga biriktirilgan bemorlar
        - ✅ Maxfiy ma'lumotlar ko'rinmaydi (pasport, telefon, email)

        **Filters:**
        - `?stage=1` - Bosqich ID
        - `?tag=2` - Tag ID
        - `?search=Aliyev` - Ism bo'yicha qidiruv
        - `?ordering=-created_at` - Saralash
        """,
        manual_parameters=[
            openapi.Parameter('stage', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description='Bosqich ID'),
            openapi.Parameter('tag', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description='Tag ID'),
            openapi.Parameter('search', openapi.IN_QUERY, type=openapi.TYPE_STRING, description='Qidiruv'),
        ],
        responses={200: PartnerPatientListSerializer(many=True)},
        tags=['partner']
    )
    def list(self, request, *args, **kwargs):
        """Bemorlar ro'yxati"""
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="👤 Bemor detail",
        operation_description="""
        Bemorning batafsil ma'lumotlari.

        **Ko'rinadi:**
        - ✅ Ism-familiya
        - ✅ Tibbiy ma'lumotlar (shikoyat, tashxis, dorilar)
        - ✅ Yuklangan hujjatlar

        **Ko'rinmaydi:**
        - ❌ Pasport
        - ❌ Telefon
        - ❌ Email
        """,
        responses={200: PartnerPatientDetailSerializer()},
        tags=['partner']
    )
    def retrieve(self, request, pk=None):
        """Bemor detail"""
        return super().retrieve(request, pk=pk)

    @swagger_auto_schema(
        operation_summary="🔄 Bosqichni o'zgartirish",
        operation_description="""
        Bemorning bosqichini o'zgartirish.

        **Request body:**
        ```json
        {
          "new_stage_code_name": "RESPONSE",
          "comment": "Tibbiy xulosa tayyor"
        }
        ```

        **Jarayon:**
        1. Bemorning bosqichi o'zgaradi
        2. Tarixga yoziladi
        """,
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['new_stage_code_name'],
            properties={
                'new_stage_code_name': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Yangi bosqich code_name',
                    enum=['DOCUMENTS', 'RESPONSE', 'TRAVEL']
                ),
                'comment': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Izoh'
                ),
            },
        ),
        responses={200: PartnerPatientDetailSerializer()},
        tags=['partner']
    )
    @action(detail=True, methods=['patch'], url_path='change-stage')
    def change_stage(self, request, pk=None):
        """Bosqichni o'zgartirish"""
        patient = self.get_object()

        # Validate
        new_stage_code_name = request.data.get('new_stage_code_name')
        comment = request.data.get('comment', '')

        if not new_stage_code_name:
            return Response(
                {"detail": "new_stage_code_name talab qilinadi"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Stage olish (code_name bo'yicha)
        try:
            new_stage = Stage.objects.get(code_name=new_stage_code_name)
        except Stage.DoesNotExist:
            return Response(
                {"detail": f"Bosqich '{new_stage_code_name}' topilmadi"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Old stage
        old_stage = patient.stage

        # Yangi stage o'rnatish
        patient.stage = new_stage
        patient.save()

        # Tarixga yozish
        history_comment = comment or f"Bosqich: {old_stage.title if old_stage else 'Yoq'} → {new_stage.title}"

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
        Hamkor tibbiy xulosa va boshqa hujjatlarni yuklaydi.

        **TZ talabi:**
        - Hamkor PDF/DOC fayl yuklaydi
        - Avtomatik bosqich "JAVOB_XATLARI" (RESPONSE) ga o'tadi
        - Tarixga yoziladi

        **Form fields:**
        - `file` (required) - PDF/DOC/DOCX fayl
        - `title` (optional) - "Tibbiy xulosa"
        - `description` (optional) - Qo'shimcha izoh
        - `document_type` (optional) - medical_report, price_list, recommendations

        **Example:**
        ```
        file: [tibbiy_xulosa.pdf]
        title: "Tibbiy xulosa"
        description: "Bemor uchun tavsiyalar"
        document_type: "medical_report"
        ```
        """,
        consumes=["multipart/form-data"],
        manual_parameters=[
            openapi.Parameter(
                "file",
                openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=True,
                description="PDF/DOC fayl (max 10MB)"
            ),
            openapi.Parameter(
                "title",
                openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Sarlavha (masalan: 'Tibbiy xulosa')"
            ),
            openapi.Parameter(
                "description",
                openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Qo'shimcha izoh"
            ),
            openapi.Parameter(
                "document_type",
                openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                enum=['medical_report', 'price_list', 'recommendations', 'other'],
                description="Hujjat turi"
            ),
        ],
        responses={
            201: PartnerResponseDocumentSerializer(),
            400: 'Noto\'g\'ri ma\'lumot',
            404: 'Bemor topilmadi',
        },
        tags=['partner']
    )
    @action(
        detail=True,
        methods=['post'],
        url_path='upload-response',
        parser_classes=[MultiPartParser, FormParser]
    )
    def upload_response(self, request, pk=None):
        """Javob xati yuklash"""
        patient = self.get_object()
        partner = request.user.partner_profile

        # Serializer
        serializer = PartnerResponseUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Document yaratish
        document = serializer.save(patient=patient, partner=partner)

        # ===============================================================
        # Bosqichni "JAVOB_XATLARI" (RESPONSE) ga o'tkazish
        # ===============================================================
        response_stage_code_name = 'RESPONSE'

        if patient.stage and patient.stage.code_name != response_stage_code_name:
            try:
                response_stage = Stage.objects.get(code_name=response_stage_code_name)
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
                logger.error(f"Stage '{response_stage_code_name}' topilmadi")

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
        operation_description="""
        Hamkorning o'z profil ma'lumotlari.

        **Ko'rinadi:**
        - Klinika/Shifokor nomi
        - Kontakt ma'lumotlar
        - Mutaxassislik
        - Statistika (jami bemorlar, faol bemorlar)
        """,
        responses={200: PartnerProfileSerializer()},
        tags=['partner']
    )
    def get(self, request, *args, **kwargs):
        """Profilni ko'rish"""
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="✏️ Profilni yangilash",
        operation_description="""
        Hamkor profil ma'lumotlarini yangilash.

        **Yangilanishi mumkin:**
        - contact_person
        - phone
        - email
        - specialization
        """,
        request_body=PartnerProfileSerializer,
        responses={200: PartnerProfileSerializer()},
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
        operation_description="""
        Hamkor tomonidan yuklangan barcha javob xatlari.

        **Filters:**
        - `?document_type=medical_report`
        - `?patient_id=17`
        """,
        responses={200: PartnerResponseDocumentSerializer(many=True)},
        tags=['partner']
    )
    def list(self, request, *args, **kwargs):
        """Javob xatlari ro'yxati"""
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="📄 Javob xati detail",
        operation_description="Bitta javob xatining batafsil ma'lumotlari",
        responses={200: PartnerResponseDocumentSerializer()},
        tags=['partner']
    )
    def retrieve(self, request, pk=None):
        """Javob xati detail"""
        return super().retrieve(request, pk=pk)