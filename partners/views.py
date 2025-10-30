# ===============================================================
# PARTNER PANEL - VIEWS (FINAL INTEGRATED)
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
from drf_yasg import openapi

from .models import PartnerResponseDocument
from .serializers import (
    PartnerPatientListSerializer,
    PartnerPatientDetailSerializer,
    PartnerResponseUploadSerializer,
    PartnerProfileSerializer,
)
from .permissions import IsPartnerUser
from patients.models import Patient, PatientHistory, PatientDocument
from core.models import Stage

import logging
logger = logging.getLogger(__name__)


# ===============================================================
# PAGINATION
# ===============================================================
class PartnerPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


# ===============================================================
# 🧩 PARTNER PANEL - DOCUMENTS BOSQICHIDAGI BEMORLAR
# ===============================================================
class PartnerPatientViewSet(viewsets.ReadOnlyModelViewSet):
    """
    🩺 Partner panel - faqat `DOCUMENTS` bosqichidagi bemorlar.
    Hamkor faqat shu bosqichdagi bemorlarga fayl yuklashi mumkin.
    """

    permission_classes = [IsAuthenticated, IsPartnerUser]
    pagination_class = PartnerPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["full_name"]
    ordering_fields = ["created_at", "updated_at", "full_name"]
    ordering = ["-updated_at"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PartnerPatientDetailSerializer
        return PartnerPatientListSerializer

    def get_queryset(self):
        """Faqat stage = DOCUMENTS bo‘lgan bemorlar"""
        document_stage = Stage.objects.filter(code_name="DOCUMENTS").first()
        return Patient.objects.filter(
            stage=document_stage,
            is_archived=False
        ).select_related("stage", "tag")

    # ===============================================================
    # 📤 Hamkor → Bemor: Fayl yuborish (DOCUMENTS → RESPONSES)
    # ===============================================================
    @swagger_auto_schema(
        operation_summary="📤 Hamkor bemorga fayl yuklaydi",
        operation_description="""
        Faqat `DOCUMENTS` bosqichidagi bemorlarga fayl yuklanadi.

        🔁 Avtomatik o‘zgarishlar:
        - Fayl `PartnerResponseDocument` va `PatientDocument`ga yoziladi
        - Bemor bosqichi `RESPONSES`ga o‘tadi
        - `PatientHistory` log yaratiladi
        """,
        manual_parameters=[
            openapi.Parameter("id", openapi.IN_PATH, description="Bemor ID", type=openapi.TYPE_INTEGER),
            openapi.Parameter("file", openapi.IN_FORM, type=openapi.TYPE_FILE, required=True, description="Fayl (PDF/PNG/DOCX)"),
            openapi.Parameter("description", openapi.IN_FORM, type=openapi.TYPE_STRING, required=False, description="Izoh (ixtiyoriy)"),
        ],
        responses={201: "Fayl muvaffaqiyatli yuklandi"},
        tags=["partner"],
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="upload",
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload(self, request, pk=None):
        """📤 Fayl yuklash (faqat stage=DOCUMENTS bo‘lsa)"""
        user = request.user
        partner = getattr(user, "partner_profile", None)
        if not partner:
            return Response({"detail": "Hamkor profili topilmadi."}, status=403)

        # ✅ Bemorni olish
        patient = get_object_or_404(Patient, id=pk, is_archived=False)
        if patient.stage.code_name != "DOCUMENTS":
            return Response({"detail": "Fayl faqat 'DOCUMENTS' bosqichidagi bemor uchun yuklanadi."}, status=400)

        # ✅ Faylni validatsiya qilish
        serializer = PartnerResponseUploadSerializer(
            data=request.data,
            context={"patient": patient, "partner": partner, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        document = serializer.save()

        # ✅ Faylni bemor hujjatlariga yozish
        PatientDocument.objects.create(
            patient=patient,
            file=document.file,
            description=document.description or "Hamkor tomonidan yuborilgan fayl",
            uploaded_by=user,
            source_type="partner",
        )

        # ✅ Stage-ni RESPONSES ga o‘tkazamiz
        response_stage, _ = Stage.objects.get_or_create(
            code_name="RESPONSES",
            defaults={"title": "Javob xatlari"},
        )
        patient.stage = response_stage
        patient.save(update_fields=["stage", "updated_at"])

        # ✅ Tarixga yozish
        PatientHistory.objects.create(
            patient=patient,
            author=user,
            comment="📄 Hamkor javob xati yukladi. Stage: DOCUMENTS → RESPONSES",
        )

        return Response({"detail": "Fayl muvaffaqiyatli yuklandi."}, status=status.HTTP_201_CREATED)


# ===============================================================
# 👤 PARTNER PROFILE
# ===============================================================
class PartnerProfileView(generics.RetrieveUpdateAPIView):
    """
    👤 Hamkor profili
    GET /api/v1/partner/profile/
    PATCH /api/v1/partner/profile/
    """

    permission_classes = [IsAuthenticated, IsPartnerUser]
    serializer_class = PartnerProfileSerializer

    def get_object(self):
        return self.request.user.partner_profile

    @swagger_auto_schema(operation_summary="👤 Hamkor profili", tags=["partner"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="✏️ Profilni yangilash", tags=["partner"])
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)
