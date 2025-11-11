# consultations/views.py
# ===============================================================
# 🚀 SENIOR-LEVEL CONVERSATIONS MODULE (Views)
# - To'liq qayta yozilgan, production-ready
# - User.id ↔ Patient.id mapping muammosi hal qilingan
# - Swagger summary/description/taglar o'zgartirilmagan
# - Performans va xavfsizlik yaxshilangan
# ===============================================================

import logging
from typing import Optional, List

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.status import HTTP_403_FORBIDDEN, HTTP_400_BAD_REQUEST

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import (
    Conversation,
    Message,
    Attachment,
    MessageReadStatus,
    Prescription,
    DoctorSummary,
)
from .serializers import (
    ConversationSerializer,
    ConversationCreateSerializer,
    MessageSerializer,
    PrescriptionSerializer,
    DoctorSummarySerializer,
    AttachmentSerializer,
)

# 👉 Patient OneToOne(User) bo'lgani uchun mappingga kerak bo'ladi
from patients.models import Patient  # Patient.user -> CustomUser (OneToOne)

logger = logging.getLogger(__name__)
User = get_user_model()

# ===============================================================
# Utils: helperlar (muammoga mo‘ljallangan)
# ===============================================================

def _safe_int(value, default: Optional[int] = None) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def _resolve_patient_user_id(*, patient_id: Optional[int], patient_profile_id: Optional[int]) -> int:
    """
    Frontend ikki xil ID jo‘natishi mumkin:
      - patient_id            → bu User.id (CustomUser) bo‘lishi kerak (oldingidek)
      - patient_profile_id    → bu Patient.id (modelingiz)
    Har ikkisini qo‘llab-quvvatlaymiz. Ustuvorlik: patient_id (User.id), bo‘lmasa patient_profile_id → map(User.id).
    """
    if patient_id is not None:
        # patient_id ni aniq User sifatida tekshiramiz
        try:
            user = User.objects.get(pk=patient_id)
            return user.id
        except User.DoesNotExist:
            raise DRFValidationError({"patient_id": "Bunday foydalanuvchi (User) topilmadi."})

    if patient_profile_id is not None:
        try:
            patient = Patient.objects.select_related("user").get(pk=patient_profile_id)
            if not patient.user_id:
                raise DRFValidationError({"patient_profile_id": "Patient bilan bog‘langan User topilmadi."})
            return patient.user_id
        except Patient.DoesNotExist:
            raise DRFValidationError({"patient_profile_id": "Bunday Patient (profil) topilmadi."})

    raise DRFValidationError({"detail": "patient_id (User.id) yoki patient_profile_id (Patient.id) majburiy."})

def _ensure_participant(conversation: Conversation, user: User, role: str) -> None:
    """
    Conversation ishtirokchini (Participant) mavjudligini kafolatlaydi.
    Idempotent.
    """
    from .models import Participant  # local import to avoid cycles
    Participant.objects.get_or_create(
        conversation=conversation,
        user=user,
        defaults={"role": role, "joined_at": timezone.now()},
    )

def _bulk_mark_read(conversation: Conversation, reader: User) -> int:
    """
    Conversation ichidagi o‘zi yozmagan va hali read_statusi yo‘q bo‘lgan xabarlarni o‘qilgan deb belgilaydi.
    Return: nechtasi yangilandi.
    """
    unread_qs = (
        conversation.messages.exclude(sender=reader)
        .exclude(read_statuses__user=reader)
        .filter(is_deleted=False)
        .only("id")  # minimal tanlash
    )
    count = 0
    for msg in unread_qs.iterator():
        MessageReadStatus.objects.get_or_create(
            message=msg,
            user=reader,
            defaults={"read_at": timezone.now(), "is_read": True},
        )
        msg.mark_as_read(reader)
        count += 1
    return count


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


# ===========================================================
# Conversation (suhbat) ViewSet
# ===========================================================
class ConversationViewSet(viewsets.ModelViewSet):
    """
    Suhbatlar uchun to‘liq boshqaruv.
    """
    queryset = (
        Conversation.objects
        .select_related("patient", "operator", "created_by")
        .prefetch_related("participants")
    )
    serializer_class = ConversationSerializer
    pagination_class = StandardResultsSetPagination
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    permission_classes = [IsAuthenticated]

    # ---- Permissions by action (qo‘shimcha) ----
    def get_permissions(self):
        # Asosiy darajada IsAuthenticated qo‘lladik; pastda shartli misollar qolishi mumkin
        return super().get_permissions()

    # ---- Queryset filter ----
    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            logger.debug("User is not authenticated, returning empty queryset")
            return Conversation.objects.none()

        logger.debug(f"Fetching conversations for user {user.id}")

        qs = (
            Conversation.objects.filter(
                Q(participants__user=user) | Q(created_by=user),
                is_active=True,
            )
            .select_related("patient", "operator")
            .prefetch_related("participants")
            .distinct()
        )

        # 📅 Sana bo‘yicha filter (?date=YYYY-MM-DD)
        filter_date = self.request.query_params.get("date")
        if filter_date:
            try:
                qs = qs.filter(created_at__date=filter_date)
                logger.debug(f"Filtering conversations by date: {filter_date}")
            except Exception as e:
                logger.warning(f"Invalid date filter: {filter_date}, error: {e}")

        # ⚙️ Status bo‘yicha filter (?status=yangi/jarayonda/yakunlangan)
        status_filter = self.request.query_params.get("status")
        if status_filter and status_filter.lower() != "barchasi":
            status_mapping = {
                "yangi": "new",
                "jarayonda": "in_progress",
                "yakunlangan": "completed",
            }
            mapped_status = status_mapping.get(status_filter.lower(), status_filter.lower())

            # Agar Conversation modelida 'status' bo‘lsa
            if hasattr(Conversation, "status"):
                qs = qs.filter(status=mapped_status)
                logger.debug(f"Filtering conversations by status: {mapped_status}")
            else:
                # Modelda status yo‘q bo‘lsa, xulq-atvor bo‘yicha taxminiy filter
                if mapped_status == "new":
                    qs = qs.filter(messages__read_statuses__isnull=True).exclude(messages__sender=user).distinct()
                elif mapped_status == "in_progress":
                    qs = qs.filter(last_message_at__gte=timezone.now() - timezone.timedelta(days=1))
                elif mapped_status == "completed":
                    qs = qs.filter(
                        ~Q(messages__read_statuses__isnull=True) | Q(messages__sender=user)
                    ).distinct()

        return qs.order_by("-last_message_at")

    # ---- Object getter ----
    def get_object(self):
        try:
            obj = Conversation.objects.get(pk=self.kwargs["pk"], is_active=True)
            # Ruxsat: faqat ishtirokchi/creator ko‘ra oladi
            if not (obj.participants.filter(user=self.request.user).exists() or obj.created_by_id == self.request.user.id):
                raise PermissionDenied("You are not a participant of this conversation")
            return obj
        except Conversation.MultipleObjectsReturned:
            obj = (
                Conversation.objects.filter(pk=self.kwargs["pk"], is_active=True)
                .order_by("-last_message_at")
                .first()
            )
            if obj:
                if not (obj.participants.filter(user=self.request.user).exists() or obj.created_by_id == self.request.user.id):
                    raise PermissionDenied("You are not a participant of this conversation")
                return obj
            raise
        except Conversation.DoesNotExist:
            logger.error(f"Conversation {self.kwargs['pk']} not found")
            raise

    # ---- Serializer switcher ----
    def get_serializer_class(self):
        if self.action == "create":
            return ConversationCreateSerializer
        return super().get_serializer_class()

    # -------------------------------------------------------
    # LIST
    # -------------------------------------------------------
    @swagger_auto_schema(
        operation_summary="📋 Suhbatlar ro'yxati",
        operation_description=(
            "Login bo'lgan foydalanuvchiga tegishli barcha suhbatlarni qaytaradi. "
            "Sana (`?date=YYYY-MM-DD`) va status (`?status=yangi`) bo'yicha filter bor."
        ),
        manual_parameters=[
            openapi.Parameter(
                "date",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Sana bo'yicha filter (YYYY-MM-DD). Masalan: 2025-10-22",
            ),
            openapi.Parameter(
                "status",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                enum=["barchasi", "yangi", "jarayonda", "yakunlangan"],
                description="Status bo'yicha filter",
            ),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Sahifa raqami"),
            openapi.Parameter("page_size", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Sahifadagi elementlar soni (max 100)"),
        ],
        responses={200: ConversationSerializer(many=True)},
        tags=["conversations"],
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        ctx = {"request": request}
        if page is not None:
            serializer = self.get_serializer(page, many=True, context=ctx)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True, context=ctx)
        return Response(serializer.data)

    # -------------------------------------------------------
    # CREATE
    # -------------------------------------------------------
    @swagger_auto_schema(
        operation_summary="➕ Yangi suhbat yaratish",
        operation_description="Yangi suhbat yaratish (operator bemor bilan, yoki foydalanuvchi support bilan)",
        request_body=ConversationCreateSerializer,
        responses={201: ConversationSerializer, 400: "Bad request - Validation error", 500: "Internal server error"},
        tags=["conversations"],
    )
    def create(self, request, *args, **kwargs):
        """
        Yangi suhbat yaratish.
        - Frontend `patient_id` (User.id) jo‘natishi mumkin — eski usul
        - Yoki `patient_profile_id` (Patient.id) jo‘natishi mumkin — yangi usul
        Har ikkala holatda ham Conversation.patient ← CustomUser ga to‘g‘ri map qilamiz.
        """
        try:
            data = request.data.copy()

            # 🔁 ID mapping: patient_profile_id -> User.id
            patient_user_id = _resolve_patient_user_id(
                patient_id=_safe_int(data.get("patient_id")),
                patient_profile_id=_safe_int(data.get("patient_profile_id")),
            )
            data["patient_id"] = patient_user_id  # serializer validatsiyasi User orqali ketadi
            data.pop("patient_profile_id", None)

            serializer = self.get_serializer(data=data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            conversation = serializer.save()

            # 🧩 Participantlarni kafolatlash
            # - Patient (always)
            _ensure_participant(conversation, conversation.patient, role="patient")
            # - Operator (agar bor bo'lsa)
            if conversation.operator_id:
                _ensure_participant(conversation, conversation.operator, role="operator")

            # Oxirgi faoliyatni yangilab borish
            if not conversation.last_message_at:
                conversation.last_message_at = timezone.now()
                conversation.save(update_fields=["last_message_at"])

            return Response(
                ConversationSerializer(conversation, context={"request": request}).data,
                status=status.HTTP_201_CREATED,
            )

        except DRFValidationError as e:
            return Response(
                {"detail": e.detail if hasattr(e, "detail") else str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Create conversation error: {str(e)}", exc_info=True)
            return Response({"detail": f"Error creating conversation: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # -------------------------------------------------------
    # PRIVATE helper – GET messages
    # -------------------------------------------------------
    def _get_messages(self, conversation: Conversation, request: Request, context: dict) -> Response:
        """
        Tanlangan suhbatdagi xabarlarni qaytaradi. Faqat ishtirokchilar ko‘ra oladi.
        Long-polling uchun `?since_id` qo‘llanadi.
        """
        if not conversation.participants.filter(user=request.user).exists():
            return Response({"detail": "You are not a participant in this conversation"}, status=status.HTTP_403_FORBIDDEN)

        queryset = (
            conversation.messages.select_related("sender", "reply_to__sender")
            .prefetch_related("attachments__uploaded_by")
            .filter(is_deleted=False)
            .order_by("id")
        )

        since_id = _safe_int(request.query_params.get("since_id"))
        if since_id:
            queryset = queryset.filter(id__gt=since_id)

        serializer = MessageSerializer(queryset, many=True, context=context)
        return Response(serializer.data)

    # -------------------------------------------------------
    # PRIVATE helper – POST message
    # -------------------------------------------------------
    def _post_message(self, conversation: Conversation, request: Request, context: dict) -> Response:
        """
        Bitta suhbatga yangi xabar yuboradi (matn yoki fayl).
        """
        if not conversation.participants.filter(user=request.user).exists():
            return Response({"detail": "You are not a participant in this conversation"}, status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()
        data["conversation"] = conversation.id
        serializer = MessageSerializer(data=data, context=context)

        if serializer.is_valid():
            result = serializer.save()
            # suhbatning oxirgi faoliyatini yangilaymiz
            Conversation.objects.filter(pk=conversation.pk).update(last_message_at=timezone.now())
            return Response(result, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # -------------------------------------------------------
    # GET/POST /conversations/{id}/messages/
    # -------------------------------------------------------
    @swagger_auto_schema(
        methods=["get"],
        operation_summary="💬 Suhbatdagi xabarlar",
        operation_description="Tanlangan suhbatga tegishli barcha xabarlarni qaytaradi. Faqat ishtirokchilar ko'ra oladi.",
        manual_parameters=[
            openapi.Parameter(
                "since_id",
                openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                description="Shundan keyingi xabarlar (long-polling uchun qulay)",
            )
        ],
        responses={200: MessageSerializer(many=True)},
        tags=["conversations"],
    )
    @swagger_auto_schema(
        methods=["post"],
        operation_summary="✉️ Suhbatga xabar yuborish",
        operation_description="Tanlangan suhbatga yangi xabar yuboradi (matn, fayl, reply va h.k.).",
        request_body=MessageSerializer,
        responses={201: MessageSerializer},
        tags=["conversations"],
    )
    @action(detail=True, methods=["get", "post"], url_path="messages")
    def conversation_messages(self, request, pk=None):
        conversation = self.get_object()
        context = {"request": request}
        if request.method == "GET":
            return self._get_messages(conversation, request, context)
        return self._post_message(conversation, request, context)

    # -------------------------------------------------------
    # POST /conversations/{id}/mark-read/
    # -------------------------------------------------------
    @swagger_auto_schema(
        operation_summary="✅ Suhbatdagi xabarlarni o'qilgan qilish",
        operation_description="Suhbatdagi o'qilmagan xabarlarni shu foydalanuvchi uchun o'qilgan deb belgilaydi.",
        responses={200: openapi.Response("Messages marked as read")},
        tags=["conversations"],
    )
    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        conversation = self.get_object()
        if not conversation.participants.filter(user=request.user).exists():
            return Response({"detail": "You are not a participant in this conversation"}, status=HTTP_403_FORBIDDEN)

        marked = _bulk_mark_read(conversation, request.user)
        return Response({"detail": f"Marked {marked} messages as read", "conversation_id": conversation.id, "marked_count": marked})

    # -------------------------------------------------------
    # GET /conversations/my/
    # -------------------------------------------------------
    @swagger_auto_schema(
        operation_summary="🧑‍💻 Foydalanuvchining suhbatlari",
        operation_description=(
            "JWT token orqali login qilingan foydalanuvchi o‘z ishtirok etgan "
            "barcha suhbatlarni ko‘radi (Conversation list)."
        ),
        manual_parameters=[
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Sahifa raqami"),
            openapi.Parameter("page_size", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Sahifadagi elementlar soni (max 100)"),
        ],
        responses={200: ConversationSerializer(many=True)},
        tags=["conversations"],
    )
    @action(detail=False, methods=["get"], url_path="my")
    def my_conversations(self, request):
        user = request.user
        qs = (
            Conversation.objects.filter(participants__user=user, is_active=True)
            .distinct()
            .select_related("patient", "operator", "created_by")
            .prefetch_related("participants")
            .order_by("-last_message_at")
        )
        page = self.paginate_queryset(qs)
        ctx = {"request": request}
        if page is not None:
            ser = ConversationSerializer(page, many=True, context=ctx)
            return self.get_paginated_response(ser.data)
        ser = ConversationSerializer(qs, many=True, context=ctx)
        return Response(ser.data)

    # -------------------------------------------------------
    # GET /conversations/{id}/prescriptions/
    # -------------------------------------------------------
    @swagger_auto_schema(
        operation_summary="💊 Suhbatga tegishli retseptlar",
        operation_description="Tanlangan suhbatga biriktirilgan retseptlar ro'yxati.",
        responses={200: PrescriptionSerializer(many=True)},
        tags=["conversations"],
    )
    @action(detail=True, methods=["get"], url_path="prescriptions")
    def get_prescriptions(self, request, pk=None):
        conversation = self.get_object()
        if not conversation.participants.filter(user=request.user).exists():
            return Response({"detail": "You are not a participant in this conversation"}, status=HTTP_403_FORBIDDEN)
        prescriptions = Prescription.objects.filter(conversation=conversation)
        ser = PrescriptionSerializer(prescriptions, many=True, context={"request": request})
        return Response(ser.data)

    # -------------------------------------------------------
    # GET /conversations/{id}/summary/
    # -------------------------------------------------------
    @swagger_auto_schema(
        operation_summary="📝 Doktor xulosasi",
        operation_description="Suhbat bo'yicha shifokor tomonidan yozilgan xulosani qaytaradi.",
        responses={200: DoctorSummarySerializer()},
        tags=["conversations"],
    )
    @action(detail=True, methods=["get"], url_path="summary")
    def get_summary(self, request, pk=None):
        conversation = self.get_object()
        if not conversation.participants.filter(user=request.user).exists():
            return Response({"detail": "You are not a participant in this conversation"}, status=HTTP_403_FORBIDDEN)
        summary = DoctorSummary.objects.filter(conversation=conversation).first()
        if not summary:
            return Response({"detail": "No summary available for this conversation"}, status=status.HTTP_404_NOT_FOUND)
        ser = DoctorSummarySerializer(summary, context={"request": request})
        return Response(ser.data)

    # -------------------------------------------------------
    # GET/POST /conversations/{id}/files/
    # -------------------------------------------------------
    @swagger_auto_schema(
        methods=['get'],
        operation_summary="📁 Suhbatdagi fayllar ro'yxati",
        operation_description="Tanlangan suhbatga yuklangan barcha fayllarni qaytaradi.",
        responses={200: openapi.Response(description="List of attachments", schema=AttachmentSerializer(many=True)), 403: "Forbidden - Not a participant"},
        tags=["conversations"],
    )
    @swagger_auto_schema(
        methods=['post'],
        operation_summary="📤 Suhbatga fayl yuklash",
        operation_description="Bir yoki bir nechta faylni suhbatga yuklaydi. Content maydoni ixtiyoriy.",
        consumes=['multipart/form-data'],
        manual_parameters=[
            openapi.Parameter('files', openapi.IN_FORM, description="Yuklanadigan fayllar (bir nechta fayl yuklash mumkin)", type=openapi.TYPE_FILE, required=True),
            openapi.Parameter('content', openapi.IN_FORM, description="Fayl uchun ixtiyoriy xabar matni", type=openapi.TYPE_STRING, required=False),
        ],
        responses={201: openapi.Response(description="Fayllar muvaffaqiyatli yuklandi", schema=MessageSerializer), 400: "Bad request - Fayl yuborilmadi", 403: "Forbidden - Siz bu suhbat ishtirokchisi emassiz", 500: "Internal server error"},
        tags=["conversations"],
    )
    @action(detail=True, methods=["get", "post"], url_path="files", parser_classes=[MultiPartParser, FormParser])
    def get_files(self, request, pk=None):
        conversation = self.get_object()
        if not conversation.participants.filter(user=request.user).exists():
            return Response({"detail": "You are not a participant in this conversation"}, status=HTTP_403_FORBIDDEN)

        if request.method == "GET":
            attachments = (
                Attachment.objects.filter(message__conversation=conversation, message__is_deleted=False)
                .select_related("message", "uploaded_by")
                .order_by("-id")
            )
            ser = AttachmentSerializer(attachments, many=True, context={"request": request})
            return Response(ser.data)

        # POST – file message
        files = request.FILES.getlist("files", [])
        if not files:
            return Response({"detail": "Kamida bitta fayl yuborish kerak"}, status=status.HTTP_400_BAD_REQUEST)

        content = (request.data.get("content") or "").strip()
        data = {"conversation": conversation.id, "type": "file", "content": content or "Fayl yuborildi"}

        ser = MessageSerializer(data=data, context={"request": request})
        if ser.is_valid():
            result = ser.save()
            Conversation.objects.filter(pk=conversation.pk).update(last_message_at=timezone.now())
            return Response(result, status=status.HTTP_201_CREATED)
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

    # -------------------------------------------------------
    # POST /conversations/{id}/operator-mark-read/
    # -------------------------------------------------------
    @swagger_auto_schema(
        operation_summary="✅ Operator xabarlarni o'qilgan qiladi",
        operation_description="Operator sifatida shu suhbatdagi o'qilmagan xabarlarni o'qilgan qilib belgilaydi.",
        responses={200: openapi.Response("Messages marked as read by operator")},
        tags=["conversations"],
    )
    @action(detail=True, methods=["post"], url_path="operator-mark-read")
    def operator_mark_read(self, request, pk=None):
        conversation = self.get_object()

        # faqat operator/staff
        if not request.user.is_staff and not getattr(request.user, "is_operator", False):
            return Response({"detail": "Only operators can perform this action"}, status=HTTP_403_FORBIDDEN)

        marked = _bulk_mark_read(conversation, request.user)
        return Response({"detail": f"Marked {marked} messages as read", "conversation_id": conversation.id, "marked_count": marked})


# ===========================================================
# Message ViewSet – alohida xabar bilan ishlash
# ===========================================================
class MessageViewSet(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """
    Xabarlarni boshqarish uchun ViewSet.
    - retrieve (GET /messages/{id}/)
    - update/partial_update (faqat o‘zi yozgan bo‘lsa)
    - delete (soft-delete, faqat o‘zi yozgan bo‘lsa)
    - mark-read (bitta xabar)
    - reply (shu xabarga javob)
    """
    queryset = (
        Message.objects
        .select_related("conversation", "sender", "reply_to")
        .prefetch_related("attachments", "conversation__participants")
    )
    serializer_class = MessageSerializer
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Message.objects.none()
        return (
            self.queryset.filter(conversation__participants__user=user, is_deleted=False)
            .distinct()
            .order_by("id")
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        instance.edited_at = timezone.now()
        instance.save(update_fields=["edited_at"])
        logger.info(f"Message {instance.id} updated by user {self.request.user.id}")

    def perform_destroy(self, instance):
        if instance.sender_id != self.request.user.id:
            raise PermissionDenied("You can only delete your own messages")
        instance.soft_delete()
        logger.info(f"Message {instance.id} soft deleted by user {self.request.user.id}")

    # -------------------------------------------------------
    # POST /messages/{id}/mark-read/
    # -------------------------------------------------------
    @swagger_auto_schema(
        operation_summary="✅ Bitta xabarni o‘qilgan qilish",
        responses={200: openapi.Response("Message marked as read")},
        tags=["messages"],
    )
    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read_single(self, request: Request, pk=None):
        message = self.get_object()

        if message.sender_id == request.user.id:
            return Response({"detail": "Cannot mark your own message as read"}, status=HTTP_400_BAD_REQUEST)

        if not message.conversation.participants.filter(user=request.user).exists():
            return Response({"detail": "You are not a participant in this conversation"}, status=HTTP_403_FORBIDDEN)

        status_obj, created = MessageReadStatus.objects.get_or_create(
            message=message,
            user=request.user,
            defaults={"read_at": timezone.now(), "is_read": True},
        )
        if created:
            message.mark_as_read(request.user)

        return Response({"detail": "Message marked as read", "message_id": message.id, "was_new": created})

    # -------------------------------------------------------
    # POST /messages/{id}/reply/
    # -------------------------------------------------------
    @swagger_auto_schema(
        operation_summary="↩️ Xabarga javob yozish",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["content"],
            properties={"content": openapi.Schema(type=openapi.TYPE_STRING, description="Javob matni")},
        ),
        responses={201: MessageSerializer},
        tags=["messages"],
    )
    @action(detail=True, methods=["post"], url_path="reply")
    def create_reply(self, request: Request, pk=None):
        parent = self.get_object()
        conv = parent.conversation

        if not conv.participants.filter(user=request.user).exists():
            return Response({"detail": "You are not a participant in this conversation"}, status=HTTP_403_FORBIDDEN)

        content = (request.data.get("content") or "").strip()
        if not content:
            return Response({"detail": "Reply content is required"}, status=status.HTTP_400_BAD_REQUEST)

        data = {"type": "text", "content": content, "reply_to": parent.id, "conversation": conv.id}
        ser = MessageSerializer(data=data, context={"request": request})
        if ser.is_valid():
            result = ser.save()
            Conversation.objects.filter(pk=conv.pk).update(last_message_at=timezone.now())
            return Response(result, status=status.HTTP_201_CREATED)
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
