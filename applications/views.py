from django.shortcuts import get_object_or_404
from rest_framework import viewsets, generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.exceptions import PermissionDenied
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Application, ApplicationHistory, Document
from .serializers import (
    ApplicationSerializer,
    ApplicationCreateUpdateSerializer,
    DocumentSerializer
)
from core.models import Stage
from patients.models import Patient


# ===============================================================
# 🧾 APPLICATION CRUD (Frontend: "Mening Tashxislarim" sahifasi)
# ===============================================================
class ApplicationViewSet(viewsets.ModelViewSet):
    """
    🩺 **Mening Tashxislarim (Arizalar) API**

    Bu API `Mening Tashxislarim` sahifasida ishlaydi.
    - Bemor o‘zi yaratgan arizalarni ko‘radi.
    - Operator va admin barcha arizalarni boshqaradi.
    """
    queryset = Application.objects.filter(is_archived=False).select_related("patient", "stage")
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return ApplicationCreateUpdateSerializer
        return ApplicationSerializer

    # ==============================================
    # 📋 Arizalar ro‘yxatini olish
    # ==============================================
    @swagger_auto_schema(
        operation_summary="📋 Arizalar ro‘yxatini olish",
        operation_description=(
            "Bemor faqat o‘z arizalarini ko‘radi, operator esa barcha arizalarni ko‘ra oladi.\n\n"
            "Bu API `Mening Tashxislarim` sahifasidagi jadvalni to‘ldirish uchun ishlatiladi."
        ),
        manual_parameters=[
            openapi.Parameter(
                "stage",
                openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                description="Filtrlash uchun Stage ID (ixtiyoriy)."
            )
        ],
        responses={200: ApplicationSerializer(many=True)},
        tags=["Applications"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        qs = Application.objects.filter(is_archived=False)

        # 🩺 Agar foydalanuvchi "patient" bo‘lsa, faqat o‘z arizalarini ko‘radi
        if getattr(user, "role", "patient") == "patient":
            # endi created_by o‘rniga Patient bilan bog‘laymiz
            patient = Patient.objects.filter(phone_number=user.phone_number).first()
            if patient:
                qs = qs.filter(patient=patient)

        return qs.select_related("patient", "stage").prefetch_related("documents", "history")

    # ==============================================
    # 🆕 Yangi ariza yaratish
    # ==============================================
    @swagger_auto_schema(
        operation_summary="🆕 Yangi ariza yaratish",
        operation_description=(
            "Bemor yangi ariza (anketa) yuboradi.\n\n"
            "Frontenddagi `Anketani to‘ldirish` tugmasi bosilganda ishlaydi."
        ),
        request_body=ApplicationCreateUpdateSerializer,
        responses={201: ApplicationSerializer},
        tags=["Applications"],
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        """
        Yangi ariza yaratish jarayoni.
        - Agar user patient bo‘lsa, Patient yozuvi aniqlanadi yoki yaratiladi
        - Default bosqich: 'yangi'
        """
        user = self.request.user  # bu CustomUser bo‘ladi
        default_stage = Stage.objects.filter(code_name="yangi").first() or Stage.objects.first()

        # 👤 Bemorni aniqlaymiz yoki yaratamiz
        if getattr(user, "role", "patient") == "patient":
            patient, _ = Patient.objects.get_or_create(created_by=user, defaults={
                "full_name": f"{user.first_name} {user.last_name}".strip(),
                "phone_number": getattr(user, "phone_number", None)
            })
        else:
            patient = serializer.validated_data.get("patient")

        # 🧾 Application saqlaymiz
        application = serializer.save(
            patient=patient,
            stage=default_stage,
            status="pending"
        )

        # 🕓 Tarixga yozuv kiritamiz (author — user bo‘lishi kerak, patient emas)
        ApplicationHistory.objects.create(
            application=application,
            author=self.request.user,  # 🔥 to‘g‘risi shu bo‘ladi!
            comment="📝 Yangi ariza yaratildi"
        )


# ===============================================================
# 📎 HUJJATLAR (Document)
# ===============================================================
class DocumentListCreateView(generics.ListCreateAPIView):
    """
    📂 **Ariza hujjatlari**
    - GET → Arizaga biriktirilgan hujjatlar ro‘yxati.
    - POST → Yangi hujjat yuklash (PDF, JPG, PNG).
    """
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        application_id = self.kwargs.get("application_id")
        return Document.objects.filter(application__id=application_id)

    @swagger_auto_schema(
        operation_summary="📎 Arizaga hujjat yuklash",
        operation_description=(
            "Fayl formatlari: PDF, JPG yoki PNG.\n\n"
            "Frontenddagi `Anketa hujjatlari` oynasida ishlaydi."
        ),
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
        tags=["Applications"],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def perform_create(self, serializer):
        application_id = self.kwargs.get("application_id")
        user = self.request.user
        application = get_object_or_404(Application, id=application_id)
        serializer.save(application=application, uploaded_by=user)
        ApplicationHistory.objects.create(application=application, author=user, comment="📄 Hujjat yuklandi")


# ===============================================================
# 🔁 BOSQICHNI O‘ZGARTIRISH (faqat admin/operator)
# ===============================================================
class ChangeApplicationStageView(APIView):
    """
    🔄 **Bosqichni o‘zgartirish API**
    Faqat operator yoki admin foydalanuvchilar foydalanadi.
    """
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="🔁 Bosqichni o‘zgartirish",
        operation_description="Arizaning bosqichini yangilaydi (masalan: 'Yangi' → 'Ko‘rib chiqilmoqda').",
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

        return Response({"success": True, "new_stage": new_stage.title}, status=status.HTTP_200_OK)
