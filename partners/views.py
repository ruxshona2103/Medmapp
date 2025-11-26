from django.shortcuts import get_object_or_404
from rest_framework import viewsets, filters, generics, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
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
from django.utils import timezone

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
    parser_classes = [MultiPartParser, FormParser, JSONParser]

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

    @swagger_auto_schema(
        operation_summary="Hamkor profili",
        operation_description="Hamkor profil ma'lumotlarini olish",
        responses={200: PartnerProfileSerializer()},
        tags=["partner"]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Profilni to'liq yangilash (Avatar bilan)",
        operation_description="Hamkor profilini to'liq yangilash. Avatar yuklash mumkin (multipart/form-data).",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'avatar': openapi.Schema(
                    type=openapi.TYPE_FILE,
                    description='Profil rasmi (PNG, JPG, JPEG)'
                ),
                'name': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Klinika/Shifokor nomi'
                ),
                'specialization': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Mutaxassislik'
                ),
                'contact_person': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Mas'ul shaxs"
                ),
                'phone': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Telefon raqam'
                ),
                'is_active': openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    description='Faol yoki faol emas'
                ),
            }
        ),
        responses={200: PartnerProfileSerializer()},
        tags=["partner"]
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Profilni qisman yangilash (Avatar bilan)",
        operation_description="Hamkor profilini qisman yangilash. Avatar yuklash mumkin (multipart/form-data).",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'avatar': openapi.Schema(
                    type=openapi.TYPE_FILE,
                    description='Profil rasmi (PNG, JPG, JPEG)'
                ),
                'name': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Klinika/Shifokor nomi'
                ),
                'specialization': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Mutaxassislik'
                ),
                'contact_person': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Mas'ul shaxs"
                ),
                'phone': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Telefon raqam'
                ),
                'is_active': openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    description='Faol yoki faol emas'
                ),
            }
        ),
        responses={200: PartnerProfileSerializer()},
        tags=["partner"]
    )
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


# ===============================================================
# OPERATOR-PARTNER CONVERSATION VIEWS
# ===============================================================

from .models import (
    OperatorPartnerConversation,
    OperatorPartnerMessage,
)
from .serializers import (
    OperatorPartnerConversationSerializer,
    OperatorPartnerConversationListSerializer,
    OperatorPartnerMessageSerializer,
    OperatorPartnerMessageCreateSerializer,
)


class OperatorPartnerConversationPagination(PageNumberPagination):
    """Suhbatlar uchun pagination"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class OperatorPartnerConversationViewSet(viewsets.ModelViewSet):
    """
    Operator va Partner o'rtasidagi suhbatlar

    - Operator o'z suhbatlarini ko'radi
    - Partner o'z suhbatlarini ko'radi
    - Yangi suhbat yaratish
    - Suhbatni ko'rish
    """
    permission_classes = [IsAuthenticated, IsPartnerOrOperator]
    pagination_class = OperatorPartnerConversationPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return OperatorPartnerConversationListSerializer
        return OperatorPartnerConversationSerializer

    def get_queryset(self):
        """
        Foydalanuvchi roliga qarab suhbatlarni filter qilish
        """
        user = self.request.user
        user_role = getattr(user, 'role', None)

        qs = OperatorPartnerConversation.objects.select_related(
            'operator', 'partner', 'created_by'
        ).prefetch_related('messages').filter(is_active=True)

        # Operator uchun - o'zi ishtirok etgan suhbatlar
        if user_role == 'operator':
            qs = qs.filter(operator=user)

        # Partner uchun - o'z profili bilan bog'liq suhbatlar
        elif user_role == 'partner':
            partner = getattr(user, 'partner_profile', None)
            if partner:
                qs = qs.filter(partner=partner)
            else:
                return OperatorPartnerConversation.objects.none()

        return qs.order_by('-last_message_at', '-created_at')

    def get_serializer_context(self):
        """Context"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @swagger_auto_schema(
        operation_summary="Suhbatlar ro'yxati",
        operation_description="Operator-Partner suhbatlar ro'yxati",
        manual_parameters=[
            openapi.Parameter('page', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Sahifa"),
            openapi.Parameter('page_size', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Sahifa hajmi"),
        ],
        responses={200: OperatorPartnerConversationListSerializer(many=True)},
        tags=["operator-partner-chat"]
    )
    def list(self, request, *args, **kwargs):
        """Suhbatlar ro'yxati"""
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Suhbat yaratish",
        operation_description="Yangi Operator-Partner suhbat yaratish",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['partner_id'],
            properties={
                'partner_id': openapi.Schema(type=openapi.TYPE_INTEGER, description="Partner ID"),
                'title': openapi.Schema(type=openapi.TYPE_STRING, description="Suhbat mavzusi"),
            }
        ),
        responses={201: OperatorPartnerConversationSerializer()},
        tags=["operator-partner-chat"]
    )
    def create(self, request, *args, **kwargs):
        """
        Yangi suhbat yaratish

        Operator yoki Partner yangi suhbat yaratishi mumkin.
        Agar suhbat allaqachon mavjud bo'lsa, mavjud suhbat qaytariladi.
        """
        user = request.user
        user_role = getattr(user, 'role', None)

        partner_id = request.data.get('partner_id')
        title = request.data.get('title', '')

        if not partner_id:
            return Response(
                {'detail': 'Partner ID kiritilishi shart'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Partner ni olish
        from .models import Partner
        try:
            partner = Partner.objects.get(id=partner_id)
        except Partner.DoesNotExist:
            return Response(
                {'detail': 'Partner topilmadi'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Operator aniqlash
        if user_role == 'operator':
            operator = user
        elif user_role == 'partner':
            # Partner suhbat yaratsa, operator tanlanishi kerak
            operator_id = request.data.get('operator_id')
            if not operator_id:
                return Response(
                    {'detail': 'Operator ID kiritilishi shart'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                operator = User.objects.get(id=operator_id, role='operator')
            except User.DoesNotExist:
                return Response(
                    {'detail': 'Operator topilmadi'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            return Response(
                {'detail': 'Faqat Operator va Partner suhbat yaratishi mumkin'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Mavjud suhbatni tekshirish
        conversation = OperatorPartnerConversation.objects.filter(
            operator=operator,
            partner=partner,
            is_active=True
        ).first()

        if conversation:
            # Mavjud suhbat qaytarish
            serializer = self.get_serializer(conversation)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Yangi suhbat yaratish
        conversation = OperatorPartnerConversation.objects.create(
            operator=operator,
            partner=partner,
            title=title,
            created_by=user
        )

        serializer = self.get_serializer(conversation)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        operation_summary="Suhbat tafsilotlari",
        operation_description="Suhbat va uning xabarlarini olish",
        responses={200: OperatorPartnerConversationSerializer()},
        tags=["operator-partner-chat"]
    )
    def retrieve(self, request, *args, **kwargs):
        """Suhbat tafsilotlari"""
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Xabar yuborish",
        operation_description="Suhbatga xabar yuborish",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['content'],
            properties={
                'content': openapi.Schema(type=openapi.TYPE_STRING, description="Xabar matni"),
                'reply_to': openapi.Schema(type=openapi.TYPE_INTEGER, description="Javob beriladigan xabar ID"),
                'type': openapi.Schema(type=openapi.TYPE_STRING, enum=['text', 'file', 'system'], description="Xabar turi"),
            }
        ),
        responses={201: OperatorPartnerMessageSerializer()},
        tags=["operator-partner-chat"]
    )
    @action(detail=True, methods=['post'], url_path='send-message')
    def send_message(self, request, pk=None):
        """
        Suhbatga xabar yuborish

        POST /api/conversations/{id}/send-message/
        """
        conversation = self.get_object()

        # Foydalanuvchi suhbatda ishtirok etayotganini tekshirish
        user = request.user
        user_role = getattr(user, 'role', None)

        if user_role == 'operator' and conversation.operator != user:
            return Response(
                {'detail': 'Bu suhbatda ishtirok eta olmaysiz'},
                status=status.HTTP_403_FORBIDDEN
            )

        if user_role == 'partner':
            partner = getattr(user, 'partner_profile', None)
            if not partner or conversation.partner != partner:
                return Response(
                    {'detail': 'Bu suhbatda ishtirok eta olmaysiz'},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Xabar yaratish
        data = request.data.copy()
        data['conversation'] = conversation.id

        serializer = OperatorPartnerMessageCreateSerializer(
            data=data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        message = serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        operation_summary="Xabarlarni o'qilgan deb belgilash",
        operation_description="Suhbatdagi barcha xabarlarni o'qilgan deb belgilash",
        responses={200: "Xabarlar o'qilgan deb belgilandi"},
        tags=["operator-partner-chat"]
    )
    @action(detail=True, methods=['post'], url_path='mark-as-read')
    def mark_as_read(self, request, pk=None):
        """
        Suhbatdagi xabarlarni o'qilgan deb belgilash

        POST /api/conversations/{id}/mark-as-read/
        """
        conversation = self.get_object()
        user = request.user

        # Foydalanuvchi yuborgan xabarlar emas, balki boshqalar yuborgan xabarlarni o'qilgan deb belgilash
        updated_count = conversation.messages.filter(
            is_read=False,
            is_deleted=False
        ).exclude(sender=user).update(is_read=True)

        return Response(
            {'detail': f'{updated_count} ta xabar o\'qilgan deb belgilandi'},
            status=status.HTTP_200_OK
        )


class OperatorPartnerMessagePagination(PageNumberPagination):
    """Xabarlar uchun pagination"""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class OperatorPartnerMessageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Operator-Partner xabarlar

    - Suhbat xabarlarini ko'rish
    - Pagination
    """
    permission_classes = [IsAuthenticated, IsPartnerOrOperator]
    serializer_class = OperatorPartnerMessageSerializer
    pagination_class = OperatorPartnerMessagePagination

    def get_queryset(self):
        """Xabarlarni filter qilish"""
        conversation_id = self.kwargs.get('conversation_id')
        if not conversation_id:
            return OperatorPartnerMessage.objects.none()

        # Foydalanuvchi suhbatda ishtirok etayotganini tekshirish
        user = self.request.user
        user_role = getattr(user, 'role', None)

        try:
            conversation = OperatorPartnerConversation.objects.get(
                id=conversation_id,
                is_active=True
            )
        except OperatorPartnerConversation.DoesNotExist:
            return OperatorPartnerMessage.objects.none()

        # Ruxsat tekshirish
        if user_role == 'operator' and conversation.operator != user:
            return OperatorPartnerMessage.objects.none()

        if user_role == 'partner':
            partner = getattr(user, 'partner_profile', None)
            if not partner or conversation.partner != partner:
                return OperatorPartnerMessage.objects.none()

        return OperatorPartnerMessage.objects.filter(
            conversation=conversation,
            is_deleted=False
        ).select_related('sender', 'reply_to').prefetch_related('attachments').order_by('created_at')

    def get_serializer_context(self):
        """Context"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @swagger_auto_schema(
        operation_summary="Suhbat xabarlari",
        operation_description="Suhbatning barcha xabarlarini olish",
        manual_parameters=[
            openapi.Parameter('page', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Sahifa"),
            openapi.Parameter('page_size', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Sahifa hajmi"),
        ],
        responses={200: OperatorPartnerMessageSerializer(many=True)},
        tags=["operator-partner-chat"]
    )
    def list(self, request, conversation_id=None):
        """Xabarlar ro'yxati"""
        return super().list(request)

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

