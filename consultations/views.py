# consultations/views.py
# ===============================================================
# 🚀 SENIOR-LEVEL CONVERSATIONS MODULE (Views) — FINAL
# - Faqat Patient.id (patient_profile_id) bilan ishlaydi
# - Hech qanday User.id ↔ Patient.id mapping YO‘Q
# - Participant yaratish kafolatlangan
# - Operator ruxsatlari tekshiriladi
# - Swagger tag/summary saqlangan
# ===============================================================

import logging
from typing import Optional

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
from rest_framework.permissions import IsAuthenticated
from rest_framework.status import HTTP_403_FORBIDDEN, HTTP_400_BAD_REQUEST, HTTP_201_CREATED

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
    ConversationCreateSerializer,   # ← Serializer faqat patient_profile_id + operator_id qabul qiladi
    MessageSerializer,
    PrescriptionSerializer,
    DoctorSummarySerializer,
    AttachmentSerializer,
)

from patients.models import Patient  # Patient.user -> CustomUser (OneToOne)

logger = logging.getLogger(__name__)
User = get_user_model()


# ===============================================================
# Helperlar
# ===============================================================
def _ensure_participant(conversation: Conversation, user: User, role: str) -> None:
    """Conversation ishtirokchisini idempotent tarzda kafolatlaydi."""
    from .models import Participant
    Participant.objects.get_or_create(
        conversation=conversation,
        user=user,
        defaults={"role": role, "joined_at": timezone.now()},
    )


def _bulk_mark_read(conversation: Conversation, reader: User) -> int:
    """Conversation ichidagi o‘zi yozmagan va hali read_statusi yo‘q xabarlarni o‘qilgan qilib belgilaydi."""
    unread_qs = (
        conversation.messages.exclude(sender=reader)
        .exclude(read_statuses__user=reader)
        .filter(is_deleted=False)
        .only("id")
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
# Conversation ViewSet
# ===========================================================
class ConversationViewSet(viewsets.ModelViewSet):
    """
    Suhbatlar uchun to‘liq boshqaruv (list, retrieve, create, custom actions).
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

    # ---- Queryset filter ----
    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Conversation.objects.none()

        qs = (
            Conversation.objects.filter(
                Q(participants__user=user) | Q(created_by=user),
                is_active=True,
            )
            .select_related("patient", "operator", "created_by")
            .prefetch_related("participants")
            .distinct()
        )

        # ⚙️ Ixtiyoriy status filtri (agar Conversation.status bo‘lsa)
        status_filter = self.request.query_params.get("status")
        if status_filter and status_filter.lower() != "barchasi":
            status_mapping = {
                "yangi": "new",
                "jarayonda": "in_progress",
                "yakunlangan": "completed",
            }
            mapped_status = status_mapping.get(status_filter.lower(), status_filter.lower())

            if hasattr(Conversation, "status"):
                qs = qs.filter(status=mapped_status)
            else:
                # Modelda status bo‘lmasa — xatti-harakat bo‘yicha taxminiy filtrlash
                if mapped_status == "new":
                    qs = qs.filter(messages__read_statuses__isnull=True).exclude(messages__sender=user).distinct()
                elif mapped_status == "in_progress":
                    qs = qs.filter(last_message_at__gte=timezone.now() - timezone.timedelta(days=1))
                elif mapped_status == "completed":
                    qs = qs.filter(~Q(messages__read_statuses__isnull=True) | Q(messages__sender=user)).distinct()

        return qs.order_by("-last_message_at", "-id")

    # ---- Serializer switcher ----
    def get_serializer_class(self):
        if self.action == "create":
            return ConversationCreateSerializer  # ← faqat patient_profile_id + operator_id
        return super().get_serializer_class()

    # -------------------------------------------------------
    # LIST
    # -------------------------------------------------------
    @swagger_auto_schema(
        operation_summary="Suhbatlar ro'yxati",
        operation_description="Foydalanuvchining barcha suhbatlari",
        manual_parameters=[
            openapi.Parameter("status", openapi.IN_QUERY, type=openapi.TYPE_STRING, enum=["barchasi", "yangi", "jarayonda", "yakunlangan"], description="Status filter"),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Sahifa"),
            openapi.Parameter("page_size", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Elementlar soni"),
        ],
        responses={200: ConversationSerializer(many=True)},
        tags=["conversations"],
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        ctx = {"request": request}
        if page is not None:
            serializer = ConversationSerializer(page, many=True, context=ctx)
            return self.get_paginated_response(serializer.data)
        serializer = ConversationSerializer(queryset, many=True, context=ctx)
        return Response(serializer.data)

    # -------------------------------------------------------
    # CREATE — faqat patient_profile_id + operator_id
    # -------------------------------------------------------
    @swagger_auto_schema(
        operation_summary="Yangi suhbat yaratish",
        operation_description="Patient ID va operator ID bilan suhbat yaratish",
        request_body=ConversationCreateSerializer,
        responses={201: ConversationSerializer, 400: "Validation error"},
        tags=["conversations"],
    )
    def create(self, request, *args, **kwargs):
        """
        Faqat `patient_profile_id` (Patient.id) + `operator_id` (User.id) qabul qiladi.
        Hech qanday User.id ↔ Patient.id mapping YO‘Q.
        """
        ser = ConversationCreateSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)

        with transaction.atomic():
            conversation = ser.save()

            # Participantlarni kafolatlaymiz (patient → patient.user, operator → operator)
            if conversation.patient and conversation.patient.user:
                _ensure_participant(conversation, conversation.patient.user, "patient")
            if conversation.operator:
                _ensure_participant(conversation, conversation.operator, "operator")

            # last_message_at bo'sh bo'lsa, hozirgi vaqtni qo'yamiz
            if not conversation.last_message_at:
                conversation.last_message_at = timezone.now()
                conversation.save(update_fields=["last_message_at"])

        return Response(
            ConversationSerializer(conversation, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    # -------------------------------------------------------
    # PRIVATE helper – GET messages
    # -------------------------------------------------------
    def _get_messages(self, conversation: Conversation, request: Request, context: dict) -> Response:
        """Tanlangan suhbatdagi xabarlar (faqat ishtirokchilar ko‘ra oladi)."""
        if not conversation.participants.filter(user=request.user).exists():
            return Response({"detail": "You are not a participant in this conversation"}, status=HTTP_403_FORBIDDEN)

        queryset = (
            conversation.messages.select_related("sender", "reply_to__sender")
            .prefetch_related("attachments__uploaded_by")
            .filter(is_deleted=False)
            .order_by("id")
        )
        since_id = request.query_params.get("since_id")
        try:
            if since_id:
                queryset = queryset.filter(id__gt=int(since_id))
        except (TypeError, ValueError):
            pass

        serializer = MessageSerializer(queryset, many=True, context=context)
        return Response(serializer.data)

    def _post_message(self, conversation: Conversation, request: Request, context: dict) -> Response:
        """Suhbatga yangi xabar yuborish (text/file)."""

        # ✅ 1) Participant emas bo‘lsa — hoziroq qo‘shib qo‘yamiz
        _ensure_participant(
            conversation,
            request.user,
            "operator" if request.user.is_staff else "patient"
        )

        # ✅ 2) Endi tekshiruv xato bermaydi
        if not conversation.participants.filter(user=request.user).exists():
            return Response({"detail": "You are not a participant in this conversation"}, status=HTTP_403_FORBIDDEN)

        # ✅ 3) Xabar yaratish oqimi
        data = request.data.copy()
        data["conversation"] = conversation.id

        serializer = MessageSerializer(data=data, context=context)
        serializer.is_valid(raise_exception=True)

        message = serializer.save()

        # ✅ 4) Oxirgi faoliyatni yangilash
        Conversation.objects.filter(pk=conversation.pk).update(last_message_at=timezone.now())

        return Response(MessageSerializer(message, context=context).data, status=status.HTTP_201_CREATED)

    # -------------------------------------------------------
    # GET/POST /conversations/{id}/messages/
    # -------------------------------------------------------
    @swagger_auto_schema(
        methods=["get"],
        operation_summary="Suhbatdagi xabarlar",
        manual_parameters=[
            openapi.Parameter("since_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Shundan keyingi xabarlar")
        ],
        responses={200: MessageSerializer(many=True)},
        tags=["conversations"],
    )
    @swagger_auto_schema(
        methods=["post"],
        operation_summary="Suhbatga xabar yuborish",
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
        operation_summary="Xabarlarni o'qilgan qilish",
        operation_description="Suhbatdagi barcha xabarlarni o'qilgan deb belgilash",
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
        operation_summary="Foydalanuvchining suhbatlari",
        operation_description="Joriy foydalanuvchi ishtirok etgan suhbatlar",
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
            .order_by("-last_message_at", "-id")
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
        operation_summary="Suhbatga tegishli retseptlar",
        operation_description="Suhbatda yozilgan barcha retseptlar",
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
        operation_summary="Doktor xulosasi",
        operation_description="Suhbat uchun doktor xulosasi",
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
        operation_summary="Suhbatdagi fayllar ro'yxati",
        responses={200: openapi.Response(description="List of attachments", schema=AttachmentSerializer(many=True)), 403: "Forbidden"},
        tags=["conversations"],
    )
    @swagger_auto_schema(
        methods=['post'],
        operation_summary="Fayl yuklash",
        consumes=['multipart/form-data'],
        manual_parameters=[
            openapi.Parameter(name='files', in_=openapi.IN_FORM, type=openapi.TYPE_FILE, description="Fayl(lar)", required=True),
            openapi.Parameter(name='content', in_=openapi.IN_FORM, type=openapi.TYPE_STRING, description="Izoh", required=False),
        ],
        responses={201: MessageSerializer, 400: "Xato", 403: "Taqiqlangan"},
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

        # --- YECHIM SHU YERDA ---
        # Avval "files" (ko'plik)ni qidiramiz
        files = request.FILES.getlist("files", [])

        # Agar "files" bo'sh bo'lsa, "file" (birlik)ni qidiramiz
        if not files:
            file_singular = request.FILES.get("file")
            if file_singular:
                files = [file_singular]  # Uni ro'yxatga o'rab qo'yamiz

        # Endi yakuniy tekshiruv
        if not files:
            return Response({"detail": "Kamida bitta fayl yuborish kerak ('file' yoki 'files' maydoni bo'lishi shart)"},
                            status=HTTP_400_BAD_REQUEST)
        # --- YECHIM TUGADI ---

        content = (request.data.get("content") or "").strip()

        # Serializer'ga 'author'ni qo'shish uchun context'ga 'request' beriladi
        # 'author' avtomatik 'request.user' bo'lishi serializer'da sozlanadi
        data = {
            "conversation": conversation.id,
            "type": "file",
            "content": content or "Fayl yuborildi"
        }

        ser = MessageSerializer(data=data, context={"request": request})
        ser.is_valid(raise_exception=True)
        msg = ser.save()  # Bu yerda serializer'ning create() metodi ishlaydi

        # Fayllarni bitta-bitta Attachment modeliga saqlaymiz
        for f in files:
            Attachment.objects.create(message=msg, uploaded_by=request.user, file=f)

        Conversation.objects.filter(pk=conversation.pk).update(last_message_at=timezone.now())
        # Yangilangan 'msg' obyektini qaytaramiz (yangi 'attachments' bilan)
        return Response(MessageSerializer(msg, context={"request": request}).data, status=HTTP_201_CREATED)

    # -------------------------------------------------------
    # POST /conversations/{id}/operator-mark-read/
    # -------------------------------------------------------
    @swagger_auto_schema(
        operation_summary="Operator xabarlarni o'qilgan qiladi",
        operation_description="Operator tomonidan xabarlarni o'qilgan deb belgilash",
        responses={200: openapi.Response("Messages marked as read by operator")},
        tags=["conversations"],
    )
    @action(detail=True, methods=["post"], url_path="operator-mark-read")
    def operator_mark_read(self, request, pk=None):
        conversation = self.get_object()
        if not request.user.is_staff and not getattr(request.user, "is_operator", False):
            return Response({"detail": "Only operators can perform this action"}, status=HTTP_403_FORBIDDEN)
        marked = _bulk_mark_read(conversation, request.user)
        return Response({"detail": f"Marked {marked} messages as read", "conversation_id": conversation.id, "marked_count": marked})


# ===========================================================
# Message ViewSet – alohida xabar bilan ishlash
# ===========================================================
class MessageViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet
):
    """
    Xabarlarni boshqarish:
    - retrieve (GET /messages/{id}/)
    - update/partial_update (faqat muallif)
    - delete (soft-delete, faqat muallif)
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
        operation_summary="Bitta xabarni o'qilgan qilish",
        operation_description="Tanlangan xabarni o'qilgan deb belgilash",
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
        operation_summary="Xabarga javob yozish",
        operation_description="Tanlangan xabarga javob yuborish",
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
        ser.is_valid(raise_exception=True)
        result = ser.save()

        Conversation.objects.filter(pk=conv.pk).update(last_message_at=timezone.now())
        return Response(result, status=status.HTTP_201_CREATED)
