import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count, Max
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import Conversation, Message, Attachment, Participant
from .serializers import (
    ConversationSerializer,
    MessageSerializer,
    AttachmentSerializer,
)

# Logger sozlash
logger = logging.getLogger(__name__)


# ============================================================
# CONVERSATION VIEWSET
# ============================================================

class ConversationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ConversationSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Conversation.objects.filter(is_active=True)

        # Role-based filtering
        if user.role == "patient":
            # Patient faqat o'zining suhbatlarini ko'radi
            queryset = queryset.filter(patient__user=user)
        elif user.role in ["operator", "admin", "superadmin"]:
            # Operator/Admin o'z suhbatlari yoki barcha suhbatlarni ko'radi
            queryset = queryset.filter(
                Q(operator=user) | Q(participants__user=user)
            ).distinct()
        else:
            # Boshqa rollar uchun bo'sh queryset
            queryset = queryset.none()

        # Optimizatsiya
        queryset = queryset.select_related(
            "patient", "operator", "created_by"
        ).prefetch_related("participants__user")

        # Annotate with message count and last message time
        queryset = queryset.annotate(
            message_count=Count("messages"),
            last_message_time=Max("messages__created_at")
        )

        return queryset.order_by("-last_message_at", "-id")

    def get_serializer_class(self):
        return ConversationSerializer

    def perform_create(self, serializer):
        """
        Yangi suhbat yaratish
        """
        user = self.request.user
        conversation = serializer.save(created_by=user, operator=user)

        # ✅ Operator va Patient uchun Participant yozuvlarini yaratish
        # Operator participant
        Participant.objects.get_or_create(
            conversation=conversation,
            user=user,
            defaults={"role": "operator"}
        )

        # Patient participant (patient.user mavjud bo'lsa)
        patient_user = getattr(conversation.patient, 'user', None)
        if patient_user:
            Participant.objects.get_or_create(
                conversation=conversation,
                user=patient_user,
                defaults={"role": "patient"}
            )

        logger.info(
            f"Conversation created | User: {user.id} | "
            f"Conversation: {conversation.id} | "
            f"Participants: Operator + Patient"
        )

    def perform_update(self, serializer):
        serializer.save()
        logger.info(
            f"Conversation updated | ID: {serializer.instance.id}"
        )

    def perform_destroy(self, instance):
        """
        Suhbatni soft delete qilish
        """
        instance.is_active = False
        instance.save(update_fields=["is_active"])

        logger.info(
            f"Conversation soft deleted | ID: {instance.id}"
        )

    # ========================================
    # CUSTOM ACTIONS
    # ========================================

    @action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        conversation = self.get_object()

        # Pagination
        limit = int(request.query_params.get("limit", 50))
        offset = int(request.query_params.get("offset", 0))

        messages = Message.objects.filter(
            conversation=conversation,
            is_deleted=False
        ).select_related(
            "sender", "reply_to"
        ).prefetch_related(
            "attachments"
        ).order_by("-created_at")[offset:offset + limit]

        serializer = MessageSerializer(
            messages,
            many=True,
            context={"request": request}
        )

        return Response({
            "conversation_id": conversation.id,
            "total_count": conversation.messages.filter(is_deleted=False).count(),
            "messages": serializer.data
        })

    @action(detail=True, methods=["post"])
    def upload_file(self, request, pk=None):
        conversation = self.get_object()
        user = request.user

        # 1. Access control
        is_participant = Participant.objects.filter(
            conversation=conversation,
            user=user
        ).exists()

        if not is_participant:
            return Response(
                {"detail": "Siz bu suhbat ishtirokchisi emassiz"},
                status=status.HTTP_403_FORBIDDEN
            )

        # 2. File validatsiya
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response(
                {"detail": "File yuklash majburiy"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # File size check (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if uploaded_file.size > max_size:
            return Response(
                {"detail": f"Fayl hajmi juda katta (max 10MB)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. Message yaratish (type=file)
        message_content = request.data.get("message", "")
        message = Message.objects.create(
            conversation=conversation,
            sender=user,
            type="file",
            content=message_content or f"File: {uploaded_file.name}"
        )

        # 4. Attachment yaratish
        attachment = Attachment.objects.create(
            message=message,
            file=uploaded_file,
            original_name=uploaded_file.name,
            size=uploaded_file.size,
            uploaded_by=user,
            mime_type=uploaded_file.content_type or "application/octet-stream"
        )

        # Auto-detect file type
        if attachment.mime_type.startswith("image/"):
            attachment.file_type = "image"
        elif attachment.mime_type.startswith("video/"):
            attachment.file_type = "video"
        elif "pdf" in attachment.mime_type or "document" in attachment.mime_type:
            attachment.file_type = "document"
        else:
            attachment.file_type = "other"
        attachment.save(update_fields=["file_type"])

        # 5. Conversation last_message_at yangilash
        conversation.last_message_at = timezone.now()
        conversation.save(update_fields=["last_message_at"])

        logger.info(
            f"=� File uploaded | User: {user.id} | "
            f"Conversation: {conversation.id} | "
            f"File: {uploaded_file.name} | "
            f"Size: {uploaded_file.size} bytes"
        )

        # ========================================
        # =� WEBSOCKET BROADCAST (CRITICAL!)
        # ========================================
        try:
            # Redis Channel Layer olish
            channel_layer = get_channel_layer()

            # Message ni serialize qilish
            message_data = MessageSerializer(
                message,
                context={"request": request}
            ).data

            group_name = f"chat_{conversation.id}"

            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "chat_message",
                    "message": message_data
                }
            )

            logger.info(
                f"=� WebSocket broadcast sent | "
                f"Group: {group_name} | "
                f"Message ID: {message.id}"
            )

        except Exception as e:
            # WebSocket broadcast xatosi logga yoziladi, lekin HTTP response fail bo'lmaydi
            logger.error(
                f"L WebSocket broadcast failed | "
                f"Conversation: {conversation.id} | "
                f"Error: {e}",
                exc_info=True
            )

        # 6. Success response
        return Response({
            "detail": "Fayl muvaffaqiyatli yuklandi",
            "message": MessageSerializer(message, context={"request": request}).data,
            "attachment": AttachmentSerializer(attachment, context={"request": request}).data
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def mark_as_read(self, request, pk=None):
        """
        Suhbatdagi barcha o'qilmagan xabarlarni o'qilgan deb belgilash

        POST /conversations/{id}/mark_as_read/
        """
        conversation = self.get_object()
        user = request.user

        # Faqat o'qilmagan xabarlarni belgilash
        unread_messages = Message.objects.filter(
            conversation=conversation,
            is_deleted=False,
            is_read_by_recipient=False
        ).exclude(sender=user)

        count = unread_messages.count()
        unread_messages.update(is_read_by_recipient=True)

        logger.info(
            f"Messages marked as read | User: {user.id} | "
            f"Conversation: {conversation.id} | "
            f"Count: {count}"
        )

        return Response({
            "detail": f"{count} ta xabar o'qilgan deb belgilandi",
            "count": count
        })


# ============================================================
# MESSAGE VIEWSET
# ============================================================

class MessageViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = MessageSerializer

    def get_queryset(self):
        """
        Foydalanuvchi faqat o'z suhbatlaridagi xabarlarni ko'radi
        """
        user = self.request.user
        conversation_id = self.request.query_params.get("conversation_id")

        # Base queryset
        queryset = Message.objects.filter(is_deleted=False)

        # Filter by conversation
        if conversation_id:
            queryset = queryset.filter(conversation_id=conversation_id)

        # Access control: faqat participant bo'lgan suhbatlar
        queryset = queryset.filter(
            Q(conversation__participants__user=user) |
            Q(conversation__patient__user=user) |
            Q(conversation__operator=user)
        ).distinct()

        # Optimizatsiya
        queryset = queryset.select_related(
            "conversation", "sender", "reply_to"
        ).prefetch_related("attachments")

        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        """
        Yangi xabar yaratish

        Note: WebSocket orqali xabar yuborish Consumer da amalga oshiriladi.
        Bu endpoint faqat HTTP fallback uchun.
        """
        user = self.request.user
        conversation = serializer.validated_data.get("conversation")

        # Access control
        is_participant = Participant.objects.filter(
            conversation=conversation,
            user=user
        ).exists()

        if not is_participant:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Siz bu suhbat ishtirokchisi emassiz")

        # Message yaratish
        message = serializer.save(sender=user)

        # Conversation last_message_at yangilash
        conversation.last_message_at = timezone.now()
        conversation.save(update_fields=["last_message_at"])

        logger.info(
            f"Message created (HTTP) | User: {user.id} | "
            f"Conversation: {conversation.id} | "
            f"Message: {message.id}"
        )

        # WebSocket broadcast (optional - asosan Consumer da)
        try:
            channel_layer = get_channel_layer()
            message_data = MessageSerializer(message, context={"request": self.request}).data

            async_to_sync(channel_layer.group_send)(
                f"chat_{conversation.id}",
                {
                    "type": "chat_message",
                    "message": message_data
                }
            )
        except Exception as e:
            logger.warning(f"WebSocket broadcast failed: {e}")

    def perform_update(self, serializer):
        """
        Xabarni tahrirlash
        """
        message = serializer.save(edited_at=timezone.now())

        logger.info(
            f"Message edited | ID: {message.id} | "
            f"User: {self.request.user.id}"
        )

    def perform_destroy(self, instance):
        """
        Xabarni soft delete qilish
        """
        instance.soft_delete()

        logger.info(
            f"Message soft deleted | ID: {instance.id} | "
            f"User: {self.request.user.id}"
        )

    @action(detail=True, methods=["post"])
    def mark_as_read(self, request, pk=None):
        """
        Xabarni o'qilgan deb belgilash

        POST /messages/{id}/mark_as_read/
        """
        message = self.get_object()
        user = request.user

        if message.sender == user:
            return Response(
                {"detail": "O'z xabaringizni o'qilgan deb belgilab bo'lmaydi"},
                status=status.HTTP_400_BAD_REQUEST
            )

        message.mark_as_read(user)

        return Response({"detail": "Xabar o'qilgan deb belgilandi"})
