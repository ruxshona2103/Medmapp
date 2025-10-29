# ===============================================================
# HAMKOR PANEL - VIEWS (code_name bilan, FINAL)
# ===============================================================
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, filters, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from rest_framework.views import APIView

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
from patients.models import Patient, PatientHistory, PatientDocument
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
# PARTNER PATIENT VIEWSET (TO‘LIQ TO‘G‘RILANGAN, ASSIGNED_PARTNER YO‘Q)
# ===============================================================
class PartnerPatientViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Hamkor paneli - Bemorlar
    - Faqat 'HUJJATLAR' (DOCUMENTS) va 'JAVOB_XATLARI' (RESPONSE) bosqichidagi bemorlar
    - assigned_partner shart emas — barcha HUJJATLAR bosqichidagilar ko‘rinadi
    """

    permission_classes = [IsAuthenticated, IsPartnerUser]
    pagination_class = PartnerPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {'stage__id': ['exact'], 'tag__id': ['exact'], 'gender': ['exact']}
    search_fields = ['full_name']
    ordering_fields = ['created_at', 'updated_at', 'full_name']
    ordering = ['-updated_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PartnerPatientDetailSerializer
        return PartnerPatientListSerializer

    def get_queryset(self):
        """✅ Faqat DOCUMENTS va RESPONSE bosqichidagilarni ko‘rsatadi (hamma hamkorlar uchun)"""
        active_stage_ids = Stage.objects.filter(
            code_name__in=['DOCUMENTS', 'RESPONSE']
        ).values_list('id', flat=True)

        queryset = Patient.objects.filter(
            stage_id__in=active_stage_ids,
            is_archived=False
        ).select_related(
            'stage', 'tag', 'assigned_partner'
        ).prefetch_related(
            'documents', 'partner_responses'
        )

        return queryset

    # ===============================================================
    # 📤 HAMKOR → RESPONSE (javob xati yuklash)
    # ===============================================================
    @swagger_auto_schema(
        operation_summary="📤 Hamkor bemorga javob xati yuklaydi",
        operation_description="""
            Faqat 'HUJJATLAR' (DOCUMENTS) bosqichidagi bemorlarga fayl yuklash mumkin.

            Avtomatik:
            - Fayl PartnerResponseDocument’ga saqlanadi
            - Fayl PatientDocument’ga ham yoziladi (operator ko‘rishi uchun)
            - Bosqich RESPONSE ga o‘tadi
            - PatientHistory log yoziladi
        """,
        manual_parameters=[
            openapi.Parameter('id', openapi.IN_PATH, description="Bemor ID", type=openapi.TYPE_INTEGER),
            openapi.Parameter('file', openapi.IN_FORM, description="Fayl (PDF/PNG/DOCX)", type=openapi.TYPE_FILE, required=True),
            openapi.Parameter('title', openapi.IN_FORM, description="Fayl nomi yoki sarlavhasi", type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('description', openapi.IN_FORM, description="Qo‘shimcha izoh", type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('document_type', openapi.IN_FORM, description="Hujjat turi", type=openapi.TYPE_STRING,
                              enum=["medical_report", "price_list", "recommendations", "other"], required=False),
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
        """📤 Hamkor bemorga javob xati yuklaydi (faqat stage = DOCUMENTS bo‘lsa)"""
        user = request.user
        partner = getattr(user, "partner_profile", None)
        if not partner:
            return Response({"detail": "Hamkor profili topilmadi."}, status=403)

        # ✅ Faqat DOCUMENTS bosqichidagi bemorlarni olish (assigned_partner kerak emas)
        try:
            patient = Patient.objects.select_related('stage').get(
                id=pk,
                stage__code_name="DOCUMENTS",
                is_archived=False
            )
        except Patient.DoesNotExist:
            return Response(
                {"detail": "Bemor topilmadi yoki u 'HUJJATLAR' bosqichida emas."},
                status=404
            )

        # ✅ Fayl validatsiya va saqlash
        serializer = PartnerResponseUploadSerializer(
            data=request.data,
            context={'request': request, 'patient': patient, 'partner': partner}
        )
        serializer.is_valid(raise_exception=True)
        document = serializer.save()

        # ✅ Fayl bemor hujjatlariga ham qo‘shiladi
        try:
            PatientDocument.objects.create(
                patient=patient,
                file=document.file,
                description=document.description or "Hamkor tomonidan yuborilgan fayl",
                uploaded_by=user,
                source_type="partner"
            )
        except Exception as e:
            logger.warning(f"PatientDocument yozishda xato: {e}")

        # ✅ Bosqichni RESPONSE ga o‘tkazamiz
        response_stage, _ = Stage.objects.get_or_create(
            code_name='RESPONSE',
            defaults={'title': 'Javob xatlari'}
        )

        old_stage = patient.stage
        if old_stage.code_name != 'RESPONSE':
            patient.stage = response_stage
            patient.save(update_fields=['stage', 'updated_at'])

            PatientHistory.objects.create(
                patient=patient,
                author=user,
                comment=f"📄 Hamkor javob xati yukladi. Bosqich: {old_stage.title} → {response_stage.title}"
            )

        # ✅ Natija qaytariladi
        output_serializer = PartnerResponseDocumentSerializer(document, context={'request': request})
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

# ===============================================================
# 📤 PARTNER → OPERATOR → PATIENT JAVOB OQIMI
# ===============================================================
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.shortcuts import get_object_or_404

from partners.models import Partner
from patients.models import Patient, PatientDocument
from .models import PartnerResponseDocument
from .serializers import PartnerResponseDocumentSerializer


# ===============================================================
# 1️⃣ PARTNER → OPERATOR: Fayl yuboradi
# ===============================================================
class PartnerUploadResponseView(APIView):
    """
    🧩 Hamkor (Partner) operator uchun javob faylini yuboradi.
    Fayl PatientDocument’ga ham qo‘shiladi (shunda operator uni ko‘ra oladi).
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        operation_summary="📤 Partner → Operator fayl yuboradi",
        operation_description="""
        Hamkor bemor uchun javob fayl yuboradi.
        Fayl avtomatik ravishda PartnerResponseDocument va PatientDocument’ga saqlanadi.
        """,
        manual_parameters=[
            openapi.Parameter(
                'id', openapi.IN_PATH, description="Bemor ID", type=openapi.TYPE_INTEGER
            )
        ],
        responses={201: "Fayl yuborildi", 403: "Faqat hamkor uchun"},
        tags=["documents"]
    )
    def post(self, request, id):
        user = request.user
        if user.role != "partner":
            return Response({"detail": "Faqat hamkor uchun."}, status=403)

        partner = Partner.objects.get(user=user)
        patient = get_object_or_404(Patient, id=id)

        file = request.FILES.get("file")
        description = request.data.get("description")

        if not file:
            return Response({"detail": "Fayl yuborilmadi."}, status=400)

        # ✅ 1. Partner javobi saqlanadi
        PartnerResponseDocument.objects.create(
            partner=partner,
            patient=patient,
            file=file,
            description=description or "Hamkor tomonidan yuborilgan fayl"
        )

        # ✅ 2. Shu fayl bemorning hujjatlariga ham yoziladi (operator ko‘rishi uchun)
        PatientDocument.objects.create(
            patient=patient,
            file=file,
            description="Hamkor tomonidan yuborilgan fayl",
            uploaded_by=user,
            source_type="partner"
        )

        return Response({"detail": "Hamkor javob faylini yubordi."}, status=201)

# ===============================================================
# 📁 RESPONSES VIEWLAR — UNIVERSAL JAVOB FAYLLAR LOGIKASI
# ===============================================================

from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from patients.models import Patient, PatientDocument
from partners.models import Partner


# ===============================================================
# 🧩 UNIVERSAL RESPONSE GET — Hamma foydalanuvchi o‘z fayllarini ko‘ra oladi
# ===============================================================
class ResponsesMyListView(APIView):
    """
    🔍 Hamma foydalanuvchi (operator, partner, patient) o‘ziga tegishli fayllarni ko‘radi.
    - Operator → o‘zi yuborgan va unga kelgan partner fayllarni ko‘radi
    - Partner → o‘zi yuborgan fayllarni va operatordan bemor fayllarini ko‘radi
    - Patient → o‘ziga yuborilgan fayllarni ko‘radi
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="📂 O‘ziga tegishli javob fayllar ro‘yxati",
        operation_description="""
        Har bir foydalanuvchi o‘z roliga qarab o‘ziga tegishli fayllarni ko‘radi:
        - `operator`: o‘zi yuborgan yoki partner yuborgan fayllar
        - `partner`: o‘zi yuborgan yoki operator yuborgan fayllar
        - `patient`: o‘ziga yuborilgan fayllar
        """,
        tags=["responses"],
        manual_parameters=[
            openapi.Parameter(
                "source",
                openapi.IN_QUERY,
                description="Filtrlash (operator, partner, patient)",
                type=openapi.TYPE_STRING
            )
        ],
        responses={200: "Foydalanuvchining javob fayllari ro‘yxati"}
    )
    def get(self, request):
        user = request.user
        role = getattr(user, "role", None)
        source = request.query_params.get("source")

        qs = PatientDocument.objects.all()

        if role == "operator" or role == "admin":
            qs = qs.filter(source_type__in=["operator", "partner"])
        elif role == "partner":
            qs = qs.filter(
                source_type__in=["partner", "operator"],
                uploaded_by=user
            ) | PatientDocument.objects.filter(source_type="operator")
        elif role in ["patient", "user"]:
            try:
                patient = Patient.objects.get(created_by=user)
                qs = qs.filter(patient=patient)
            except Patient.DoesNotExist:
                return Response({"detail": "Bemor topilmadi"}, status=404)
        else:
            return Response({"detail": "Noma’lum foydalanuvchi roli"}, status=403)

        if source:
            qs = qs.filter(source_type=source)

        data = [
            {
                "id": d.id,
                "file_url": request.build_absolute_uri(d.file.url) if d.file else None,
                "patient": d.patient.full_name if d.patient else None,
                "source": d.source_type,
                "description": d.description,
                "uploaded_by": getattr(d.uploaded_by, "username", None),
                "uploaded_at": d.uploaded_at,
            }
            for d in qs.order_by("-uploaded_at")
        ]

        return Response(data, status=200)


# ===============================================================
# 🧾 Partner → Operator fayl yuboradi
# ===============================================================
# ===============================================================
# 🧾 Partner → Operator fayl yuboradi (TO‘G‘RILANGAN)
# ===============================================================
from rest_framework import serializers

class PartnerSendResponseSerializer(serializers.Serializer):
    """Swagger uchun serializer (fayl upload shaklida chiqishi uchun)"""
    file = serializers.FileField(required=True, help_text="Yuklanadigan fayl (PDF, PNG, DOCX va h.k.)")
    description = serializers.CharField(required=False, allow_blank=True, help_text="Qo‘shimcha izoh")


class PartnerSendResponseView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        operation_summary="📤 Partner → Operator fayl yuboradi",
        operation_description="""
            Hamkor bemor uchun operatorga fayl yuboradi. Fayl avtomatik ravishda:
            - `PartnerResponseDocument` va `PatientDocument` jadvaliga saqlanadi.
            - Operator ham faylni ko‘ra oladi.
        """,
        tags=["responses"],
        request_body=PartnerSendResponseSerializer,  # ✅ Fayl tanlash uchun
        responses={
            201: openapi.Response("Fayl operatorga yuborildi"),
            400: openapi.Response("Fayl tanlanmagan yoki noto‘g‘ri"),
            403: openapi.Response("Faqat hamkor uchun")
        }
    )
    def post(self, request, patient_id):
        user = request.user
        if getattr(user, "role", None) != "partner":
            return Response({"detail": "Faqat hamkor uchun."}, status=403)

        partner = Partner.objects.filter(user=user).first()
        if not partner:
            return Response({"detail": "Hamkor topilmadi."}, status=404)

        patient = get_object_or_404(Patient, id=patient_id)

        # Fayl tekshirish
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "Fayl tanlanmagan."}, status=400)

        description = request.data.get("description")

        # ✅ Fayl saqlash
        response_doc = PartnerResponseDocument.objects.create(
            partner=partner,
            patient=patient,
            file=file,
            description=description or "Hamkor tomonidan yuborilgan fayl"
        )

        # ✅ Faylni PatientDocument ga ham yozish (operator ko‘rishi uchun)
        PatientDocument.objects.create(
            patient=patient,
            file=file,
            description=description or "Hamkor tomonidan yuborilgan hujjat",
            uploaded_by=user,
            source_type="partner"
        )

        return Response(
            {"detail": "Hamkor fayl yubordi.", "file_url": request.build_absolute_uri(response_doc.file.url)},
            status=201
        )

# ===============================================================
# 🧾 Operator → Bemor fayl yuboradi
# ===============================================================
class OperatorSendResponseView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        operation_summary="📤 Operator → Bemorga fayl yuboradi",
        operation_description="Operator bemorga rasmiy fayl yuboradi.",
        tags=["responses"],
        manual_parameters=[
            openapi.Parameter("patient_id", openapi.IN_PATH, description="Bemor ID", type=openapi.TYPE_INTEGER)
        ],
        responses={201: "Fayl bemorga yuborildi", 403: "Faqat operator uchun"}
    )
    def post(self, request, patient_id):
        user = request.user
        if user.role not in ["operator", "admin"]:
            return Response({"detail": "Faqat operator uchun."}, status=403)

        patient = get_object_or_404(Patient, id=patient_id)
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "Fayl tanlanmagan."}, status=400)

        description = request.data.get("description")

        PatientDocument.objects.create(
            patient=patient,
            file=file,
            description=description or "Operator tomonidan yuborilgan hujjat",
            uploaded_by=user,
            source_type="operator"
        )

        return Response({"detail": "Fayl bemorga yuborildi."}, status=201)
