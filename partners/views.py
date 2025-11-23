from django.shortcuts import get_object_or_404
from rest_framework import viewsets, filters, generics, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response

from .models import PartnerResponseDocument
from .serializers import (
    PartnerPatientListSerializer,
    PartnerPatientDetailSerializer,
    PartnerResponseUploadSerializer,
    PartnerProfileSerializer, PartnerResponseSerializer
)
from patients.models import Patient, PatientHistory, PatientDocument
from core.models import Stage
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .permissions import IsPartnerUser, IsPartnerOrOperator


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
    permission_classes = [IsAuthenticated, IsPartnerOrOperator]
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
        operation_summary="Hamkor bemorga fayl yuklaydi",
        operation_description="DOCUMENTS bosqichidagi bemorga fayl yuklash",
        manual_parameters=[
            openapi.Parameter("id", openapi.IN_PATH, description="Bemor ID", type=openapi.TYPE_INTEGER),
            openapi.Parameter("file", openapi.IN_FORM, type=openapi.TYPE_FILE, required=True, description="Fayl"),
            openapi.Parameter("description", openapi.IN_FORM, type=openapi.TYPE_STRING, required=False, description="Izoh"),
        ],
        responses={201: "Fayl yuklandi"},
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


class PartnerProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, IsPartnerUser]
    serializer_class = PartnerProfileSerializer

    def get_object(self):
        from partners.models import Partner
        user = self.request.user
        profile, created = Partner.objects.get_or_create(
            user=user,
            defaults={
                'name': user.first_name or user.phone_number or f'Partner_{user.id}',
                'code': f'PARTNER_{user.id}',
                'phone': getattr(user, 'phone_number', None),
            }
        )
        return profile

    @swagger_auto_schema(operation_summary="Hamkor profili", operation_description="Hamkor profil ma'lumotlarini olish", tags=["partner"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Profilni to'liq yangilash", operation_description="Hamkor profilini to'liq yangilash", tags=["partner"])
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Profilni qisman yangilash", operation_description="Hamkor profilini qisman yangilash", tags=["partner"])
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)



class PartnerResponseViewSet(viewsets.ReadOnlyModelViewSet):
    """
    📩 Hamkor yuborgan javob xatlari (PartnerResponseDocument)
    """

    permission_classes = [IsAuthenticated, IsPartnerOrOperator]
    serializer_class = PartnerResponseSerializer
    queryset = PartnerResponseDocument.objects.select_related("patient", "partner").order_by("-uploaded_at")

    @swagger_auto_schema(
        tags=["partner"],
        operation_summary="Hamkor javob xatlari ro'yxati",
        operation_description="Hamkor yuklagan barcha javob xatlari",
        manual_parameters=[
            openapi.Parameter("patient_id", openapi.IN_QUERY, description="Bemor ID bo'yicha filter", type=openapi.TYPE_INTEGER, required=False),
        ],
        responses={200: PartnerResponseSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        # Operator/admin uchun - barcha responslar
        if hasattr(request.user, 'role') and request.user.role in ('operator', 'admin'):
            qs = self.queryset.all()
        # Hamkor uchun - faqat o'z responslar
        else:
            partner = getattr(request.user, "partner_profile", None)
            if not partner:
                return Response({"detail": "Hamkor profili topilmadi."}, status=status.HTTP_403_FORBIDDEN)
            qs = self.queryset.filter(partner=partner)

        # 🔍 Filter by patient_id (optional)
        patient_id = request.query_params.get("patient_id")
        if patient_id:
            qs = qs.filter(patient_id=patient_id)

        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page or qs, many=True, context={"request": request})
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        tags=["partner"],
        operation_summary="Bitta javob xatini olish",
        operation_description="ID orqali javob xati ma'lumotlarini olish",
        responses={200: PartnerResponseSerializer()},
    )
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        # Operator/admin uchun - barcha responslarni ko'rish mumkin
        if hasattr(request.user, 'role') and request.user.role in ('operator', 'admin'):
            serializer = self.get_serializer(instance, context={"request": request})
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Hamkor uchun - faqat o'z responslarni ko'rish mumkin
        partner = getattr(request.user, "partner_profile", None)
        if not partner:
            return Response({"detail": "Hamkor profili topilmadi."}, status=status.HTTP_403_FORBIDDEN)

        if instance.partner != partner:
            return Response({"detail": "Bu fayl sizga tegishli emas."}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(instance, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        tags=["partner"],
        operation_summary="Bemor javob xatlari",
        operation_description="Bemorga tegishli barcha javob xatlari",
        responses={200: PartnerResponseSerializer(many=True)},
    )
    def patient_responses(self, request, patient_id=None):
        # Operator/admin uchun - barcha patient responslar
        if hasattr(request.user, 'role') and request.user.role in ('operator', 'admin'):
            qs = self.queryset.filter(patient_id=patient_id)
        # Hamkor uchun - faqat o'z patient responslar
        else:
            partner = getattr(request.user, "partner_profile", None)
            if not partner:
                return Response({"detail": "Hamkor profili topilmadi."}, status=status.HTTP_403_FORBIDDEN)
            qs = self.queryset.filter(partner=partner, patient_id=patient_id)

        serializer = self.get_serializer(qs, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

