from django.db.models import Q
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.status import HTTP_403_FORBIDDEN, HTTP_400_BAD_REQUEST

from .models import (
    Conversation,
    Message,
    Attachment,
    MessageReadStatus,
    Participant,
    Prescription,
    DoctorSummary,
)
from .serializers import (
    ConversationSerializer,
    ConversationCreateSerializer,
    MessageSerializer,
    MessageReadStatusSerializer,
    PrescriptionSerializer,
    DoctorSummarySerializer,
    AttachmentSerializer,
    UserTinySerializer,
)

import logging

logger = logging.getLogger(__name__)

User = get_user_model()


class StandardResultsSetPagination(PageNumberPagination):
    """
    Pagination konfiguratsiyasi.
    """
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class ConversationViewSet(viewsets.ModelViewSet):
    """
    Conversation ViewSet.
    Suhbatlarni boshqarish uchun.
    """
    queryset = Conversation.objects.select_related(
        "patient", "operator", "created_by"
    ).prefetch_related("participants")
    serializer_class = ConversationSerializer
    pagination_class = StandardResultsSetPagination
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_permissions(self):
        if self.action in [
            "get_messages",
            "post_message",
            "mark_read",
            "get_prescriptions",
            "get_summary",
            "get_files",
            "operator_mark_read",
            "operator_conversation_messages",
        ]:
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            logger.debug("User is not authenticated, returning empty queryset")
            return Conversation.objects.none()

        logger.debug(f"Fetching conversations for user {user.id}")
        qs = (
            Conversation.objects.filter(
                Q(participants__user=user) | Q(created_by=user), is_active=True
            )
            .select_related("patient", "operator")
            .prefetch_related("participants")
            .distinct()
        )

        # 📅 Sana bo'yicha filter
        filter_date = self.request.query_params.get("date")
        if filter_date:
            try:
                qs = qs.filter(created_at__date=filter_date)
                logger.debug(f"Filtering conversations by date: {filter_date}")
            except Exception as e:
                logger.warning(f"Invalid date filter: {filter_date}, error: {e}")

        # ⚙️ Status bo'yicha filter
        status_filter = self.request.query_params.get("status")
        if status_filter and status_filter.lower() != "barchasi":
            status_mapping = {
                "yangi": "new",
                "jarayonda": "in_progress",
                "yakunlangan": "completed",
            }
            mapped_status = status_mapping.get(status_filter.lower(), status_filter.lower())

            # Agar Conversation modelida status field bo'lsa
            if hasattr(Conversation, 'status'):
                qs = qs.filter(status=mapped_status)
                logger.debug(f"Filtering conversations by status: {mapped_status}")
            else:
                # Agar status field yo'q bo'lsa, unread_count yoki boshqa logika bo'yicha filter
                if mapped_status == "new":
                    # Yangi - o'qilmagan xabarlar bor
                    qs = qs.filter(
                        messages__read_status__isnull=True
                    ).exclude(messages__sender=user).distinct()
                elif mapped_status == "in_progress":
                    # Jarayonda - oxirgi xabar 24 soat ichida
                    qs = qs.filter(
                        last_message_at__gte=timezone.now() - timezone.timedelta(days=1)
                    )
                elif mapped_status == "completed":
                    # Yakunlangan - barcha xabarlar o'qilgan
                    qs = qs.filter(
                        ~Q(messages__read_status__isnull=True) | Q(messages__sender=user)
                    ).distinct()

        return qs.order_by("-last_message_at")

    def get_object(self):
        try:
            logger.debug(f"Attempting to get conversation with pk={self.kwargs['pk']}")
            obj = Conversation.objects.get(
                pk=self.kwargs['pk'],
                is_active=True
            )
            self.check_object_permissions(self.request, obj)
            logger.debug(f"Found conversation: {obj.id}")
            return obj
        except Conversation.MultipleObjectsReturned:
            logger.warning(f"Multiple active conversations found for pk={self.kwargs['pk']}")
            obj = Conversation.objects.filter(
                pk=self.kwargs['pk'],
                is_active=True
            ).order_by('-last_message_at').first()
            if obj:
                self.check_object_permissions(self.request, obj)
                logger.debug(f"Selected most recent conversation: {obj.id}")
                return obj
            raise
        except Conversation.DoesNotExist:
            logger.error(f"Conversation {self.kwargs['pk']} not found")
            raise

    def get_serializer_class(self):
        if self.action == "create":
            return ConversationCreateSerializer
        return super().get_serializer_class()

    @swagger_auto_schema(
        operation_summary="📋 Barcha suhbatlarni olish",
        operation_description="Autentifikatsiya qilingan foydalanuvchi uchun barcha suhbatlarni ko'rish. Sana va status bo'yicha filter qo'llab-quvvatlanadi.",
        manual_parameters=[
            openapi.Parameter(
                "date",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Sana bo'yicha filter (YYYY-MM-DD formatda). Misol: 2025-10-22"
            ),
            openapi.Parameter(
                "status",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                enum=["barchasi", "yangi", "jarayonda", "yakunlangan"],
                description="Status bo'yicha filter: Barchasi, Yangi, Jarayonda, Yakunlangan"
            ),
            openapi.Parameter(
                "page",
                openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                description="Sahifa raqami"
            ),
            openapi.Parameter(
                "page_size",
                openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                description="Sahifadagi elementlar soni (max 100)"
            ),
        ],
        responses={200: ConversationSerializer(many=True)},
        tags=["conversations"]
    )
    def list(self, request, *args, **kwargs):
        try:
            logger.debug(f"Listing conversations for user {request.user.id}")
            queryset = self.get_queryset()

            # Pagination qo'llash
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True, context={"request": request})
                logger.info(f"Retrieved {len(page)} conversations (paginated)")
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(queryset, many=True, context={"request": request})
            logger.info(f"Retrieved {queryset.count()} conversations")
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error in list conversations: {str(e)}", exc_info=True)
            return Response(
                {"detail": f"Error retrieving conversations: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def create(self, request: Request, *args, **kwargs):
        try:
            user_id = request.user.id
            logger.debug(f"Creating conversation for user {user_id}")
            serializer = self.get_serializer(data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            conversation = serializer.save()
            logger.info(f"Created conversation {conversation.id} for user {user_id}")
            return Response(
                ConversationSerializer(conversation, context={"request": request}).data,
                status=status.HTTP_201_CREATED,
            )
        except DRFValidationError as e:
            logger.error(f"Validation error: {str(e)}")
            return Response(
                {"detail": str(e.detail) if hasattr(e, "detail") else str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Create conversation error: {str(e)}", exc_info=True)
            return Response(
                {"detail": f"Error creating conversation: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _get_messages(self, conversation, request, context):
        try:
            logger.debug(f"Getting messages for conversation {conversation.id}, user {request.user.id}")

            if not conversation.participants.filter(user=request.user).exists():
                logger.warning(
                    f"User {request.user.id} is not a participant in conversation {conversation.id}"
                )
                return Response(
                    {"detail": "You are not a participant in this conversation"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            queryset = (
                conversation.messages.select_related("sender", "reply_to__sender")
                .prefetch_related("attachments__uploaded_by")
                .filter(is_deleted=False)
                .order_by("id")
            )

            since_id = request.query_params.get("since_id")
            if since_id:
                try:
                    queryset = queryset.filter(id__gt=int(since_id))
                    logger.debug(f"Filtering messages after ID {since_id}")
                except (ValueError, TypeError):
                    logger.warning(f"Invalid since_id: {since_id}")

            serializer = MessageSerializer(queryset, many=True, context=context)
            logger.info(f"Retrieved {queryset.count()} messages for conversation {conversation.id}")
            return Response(serializer.data)

        except Exception as e:
            logger.error(f"Error in _get_messages: {str(e)}", exc_info=True)
            return Response(
                {"detail": f"Error retrieving messages: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _post_message(self, conversation, request, context):
        try:
            logger.debug(f"Posting message to conversation {conversation.id}")

            if not conversation.participants.filter(user=request.user).exists():
                logger.warning(
                    f"User {request.user.id} is not a participant in conversation {conversation.id}"
                )
                return Response(
                    {"detail": "You are not a participant in this conversation"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            data = request.data.copy()
            data["conversation"] = conversation.id

            serializer = MessageSerializer(data=data, context=context)

            if serializer.is_valid():
                result = serializer.save()
                logger.info(f"Message created successfully in conversation {conversation.id}")
                return Response(result, status=status.HTTP_201_CREATED)
            else:
                logger.error(f"Message serializer errors: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Error in _post_message: {str(e)}", exc_info=True)
            return Response(
                {"detail": f"Error sending message: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        operation_summary="Get messages in a conversation",
        operation_description="Retrieve all messages in a conversation",
        manual_parameters=[
            openapi.Parameter(
                "since_id",
                openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                description="Retrieve messages with ID greater than this value",
            )
        ],
        responses={200: MessageSerializer(many=True)},
        tags=["conversations"]
    )
    @action(detail=True, methods=["get"], url_path="messages")
    def get_messages(self, request: Request, pk=None):
        conversation = self.get_object()
        context = {"request": request}
        return self._get_messages(conversation, request, context)

    @swagger_auto_schema(
        operation_summary="Post a message to a conversation",
        operation_description="Send a new message in a conversation",
        request_body=MessageSerializer,
        responses={201: MessageSerializer},
        tags=["conversations"]
    )
    @action(detail=True, methods=["post"], url_path="messages")
    def post_message(self, request: Request, pk=None):
        conversation = self.get_object()
        context = {"request": request}
        return self._post_message(conversation, request, context)

    @swagger_auto_schema(
        operation_summary="Mark conversation messages as read",
        operation_description="Mark all unread messages in a conversation as read",
        responses={200: openapi.Response("Messages marked as read")},
        tags=["conversations"]
    )
    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request: Request, pk=None):
        try:
            conversation = self.get_object()
            logger.debug(f"mark_read called for conversation {conversation.id}")

            if not conversation.participants.filter(user=request.user).exists():
                logger.warning(
                    f"User {request.user.id} is not a participant in conversation {conversation.id}"
                )
                return Response(
                    {"detail": "You are not a participant in this conversation"},
                    status=HTTP_403_FORBIDDEN,
                )

            unread_messages = conversation.messages.exclude(
                sender=request.user
            ).exclude(
                read_status__user=request.user
            ).filter(is_deleted=False)

            marked_count = 0
            for message in unread_messages:
                MessageReadStatus.objects.get_or_create(
                    message=message,
                    user=request.user,
                    defaults={"read_at": timezone.now()},
                )
                message.mark_as_read(request.user)
                marked_count += 1

            logger.info(
                f"Marked {marked_count} messages as read in conversation {conversation.id}"
            )
            return Response(
                {
                    "detail": f"Marked {marked_count} messages as read",
                    "conversation_id": conversation.id,
                    "marked_count": marked_count,
                }
            )
        except Exception as e:
            logger.error(f"Error in mark_read: {str(e)}", exc_info=True)
            return Response(
                {"detail": f"Error marking messages as read: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        operation_summary="Get prescriptions in a conversation",
        operation_description="Retrieve all prescriptions shared in a conversation",
        responses={200: PrescriptionSerializer(many=True)},
        tags=["conversations"]
    )
    @action(detail=True, methods=["get"], url_path="prescriptions")
    def get_prescriptions(self, request: Request, pk=None):
        try:
            conversation = self.get_object()
            logger.debug(f"get_prescriptions called for conversation {conversation.id}")

            if not conversation.participants.filter(user=request.user).exists():
                logger.warning(
                    f"User {request.user.id} is not a participant in conversation {conversation.id}"
                )
                return Response(
                    {"detail": "You are not a participant in this conversation"},
                    status=HTTP_403_FORBIDDEN,
                )

            prescriptions = Prescription.objects.filter(conversation=conversation)
            serializer = PrescriptionSerializer(
                prescriptions, many=True, context={"request": request}
            )
            logger.info(
                f"Retrieved {prescriptions.count()} prescriptions for conversation {conversation.id}"
            )
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error in get_prescriptions: {str(e)}", exc_info=True)
            return Response(
                {"detail": f"Error retrieving prescriptions: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        operation_summary="Get doctor summary for a conversation",
        operation_description="Retrieve doctor's summary for a conversation",
        responses={200: DoctorSummarySerializer()},
        tags=["conversations"]
    )
    @action(detail=True, methods=["get"], url_path="summary")
    def get_summary(self, request: Request, pk=None):
        try:
            conversation = self.get_object()
            logger.debug(f"get_summary called for conversation {conversation.id}")

            if not conversation.participants.filter(user=request.user).exists():
                logger.warning(
                    f"User {request.user.id} is not a participant in conversation {conversation.id}"
                )
                return Response(
                    {"detail": "You are not a participant in this conversation"},
                    status=HTTP_403_FORBIDDEN,
                )

            summary = DoctorSummary.objects.filter(conversation=conversation).first()
            if not summary:
                logger.info(f"No summary found for conversation {conversation.id}")
                return Response(
                    {"detail": "No summary available for this conversation"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = DoctorSummarySerializer(summary, context={"request": request})
            logger.info(f"Retrieved summary for conversation {conversation.id}")
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error in get_summary: {str(e)}", exc_info=True)
            return Response(
                {"detail": f"Error retrieving summary: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        operation_summary="Get files in a conversation",
        operation_description="Retrieve all file attachments in a conversation",
        responses={200: AttachmentSerializer(many=True)},
        tags=["conversations"]
    )
    @action(detail=True, methods=["get"], url_path="files")
    def get_files(self, request: Request, pk=None):
        try:
            conversation = self.get_object()
            logger.debug(f"get_files called for conversation {conversation.id}")

            if not conversation.participants.filter(user=request.user).exists():
                logger.warning(
                    f"User {request.user.id} is not a participant in conversation {conversation.id}"
                )
                return Response(
                    {"detail": "You are not a participant in this conversation"},
                    status=HTTP_403_FORBIDDEN,
                )

            attachments = Attachment.objects.filter(
                message__conversation=conversation, message__is_deleted=False
            ).select_related("message", "uploaded_by")

            serializer = AttachmentSerializer(
                attachments, many=True, context={"request": request}
            )
            logger.info(
                f"Retrieved {attachments.count()} files for conversation {conversation.id}"
            )
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error in get_files: {str(e)}", exc_info=True)
            return Response(
                {"detail": f"Error retrieving files: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        operation_summary="Operator marks conversation as read",
        operation_description="Mark all unread messages in a conversation as read (operator action)",
        responses={200: openapi.Response("Messages marked as read by operator")},
        tags=["conversations"]
    )
    @action(detail=True, methods=["post"], url_path="operator-mark-read")
    def operator_mark_read(self, request: Request, pk=None):
        try:
            conversation = self.get_object()
            logger.debug(f"operator_mark_read called for conversation {conversation.id}")

            if not request.user.is_staff and not hasattr(request.user, "is_operator"):
                logger.warning(
                    f"User {request.user.id} is not authorized for operator actions"
                )
                return Response(
                    {"detail": "Only operators can perform this action"},
                    status=HTTP_403_FORBIDDEN,
                )

            unread_messages = conversation.messages.exclude(
                sender=request.user
            ).exclude(
                read_status__user=request.user
            ).filter(is_deleted=False)

            marked_count = 0
            for message in unread_messages:
                MessageReadStatus.objects.get_or_create(
                    message=message,
                    user=request.user,
                    defaults={"read_at": timezone.now()},
                )
                message.mark_as_read(request.user)
                marked_count += 1

            logger.info(
                f"Operator marked {marked_count} messages as read in conversation {conversation.id}"
            )
            return Response(
                {
                    "detail": f"Marked {marked_count} messages as read",
                    "conversation_id": conversation.id,
                    "marked_count": marked_count,
                }
            )
        except Exception as e:
            logger.error(f"Error in operator_mark_read: {str(e)}", exc_info=True)
            return Response(
                {"detail": f"Error marking messages as read: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        methods=["get"],
        operation_summary="Operator conversation messages (GET)",
        operation_description="Get messages in operator-patient conversation",
        manual_parameters=[
            openapi.Parameter(
                "since_id",
                openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                description="Retrieve messages with ID greater than this value",
            )
        ],
        responses={200: MessageSerializer(many=True)},
        tags=["conversations"]
    )
    @swagger_auto_schema(
        methods=["post"],
        operation_summary="Operator conversation messages (POST)",
        operation_description="Post message in operator-patient conversation",
        request_body=MessageSerializer,
        responses={201: MessageSerializer},
        tags=["conversations"]
    )
    @action(detail=False, methods=["get", "post"], url_path="operator/(?P<patient_id>[^/.]+)")
    def operator_conversation_messages(self, request: Request, patient_id=None):
        try:
            logger.debug(
                f"operator_conversation_messages called for patient {patient_id}"
            )

            if not request.user.is_staff and not hasattr(request.user, "is_operator"):
                logger.warning(
                    f"User {request.user.id} is not authorized for operator actions"
                )
                return Response(
                    {"detail": "Only operators can perform this action"},
                    status=HTTP_403_FORBIDDEN,
                )

            patient = get_object_or_404(User, pk=patient_id)
            logger.debug(f"Found patient: {patient.get_full_name()}")

            conversation = Conversation.objects.filter(
                patient=patient,
                operator=request.user,
                is_active=True
            ).order_by('-last_message_at').first()

            if not conversation:
                logger.info(f"No active conversation found, creating new one for patient {patient_id}")
                conversation = Conversation.objects.create(
                    patient=patient,
                    operator=request.user,
                    created_by=request.user,
                    title=f"Operator conversation: {patient.get_full_name() or patient.username or f'User {patient_id}'}",
                    last_message_at=timezone.now(),
                )
                Participant.objects.get_or_create(
                    conversation=conversation,
                    user=patient,
                    defaults={"role": "patient", "joined_at": timezone.now()},
                )
                Participant.objects.get_or_create(
                    conversation=conversation,
                    user=request.user,
                    defaults={"role": "operator", "joined_at": timezone.now()},
                )
                welcome_message = Message.objects.create(
                    conversation=conversation,
                    sender=request.user,
                    type="system",
                    content=f"Hello! I am operator {request.user.get_full_name() or request.user.username}. Ready to assist you. How can I help?",
                )
                MessageReadStatus.objects.create(
                    message=welcome_message,
                    user=request.user,
                    read_at=timezone.now(),
                )
                logger.info(f"Created conversation {conversation.id} with welcome message")

            context = {"request": request}

            if request.method == "GET":
                return self._get_messages(conversation, request, context)
            elif request.method == "POST":
                return self._post_message(conversation, request, context)

        except Exception as e:
            logger.error(f"Error in operator_conversation_messages: {str(e)}", exc_info=True)
            return Response(
                {"detail": f"Error in operator conversation: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class MessageViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Message ViewSet.
    Xabarlarni boshqarish uchun.
    """
    queryset = Message.objects.select_related(
        "conversation", "sender", "reply_to"
    ).prefetch_related("attachments")
    serializer_class = MessageSerializer
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    pagination_class = StandardResultsSetPagination

    def get_permissions(self):
        if self.action in ["mark_read_single", "create_reply"]:
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            logger.debug("User is not authenticated, returning empty queryset")
            return Message.objects.none()

        logger.debug(f"Fetching messages for user {user.id}")
        return self.queryset.filter(
            conversation__participants__user=user, is_deleted=False
        ).order_by("id")

    def perform_update(self, serializer):
        instance = serializer.save()
        instance.edited_at = timezone.now()
        instance.save(update_fields=["edited_at"])
        logger.info(f"Message {instance.id} updated by user {self.request.user.id}")

    def perform_destroy(self, instance):
        if instance.sender != self.request.user:
            logger.warning(
                f"User {self.request.user.id} attempted to delete message {instance.id} not owned by them"
            )
            raise PermissionDenied("You can only delete your own messages")
        instance.soft_delete()
        logger.info(f"Message {instance.id} soft deleted by user {self.request.user.id}")

    @swagger_auto_schema(
        operation_summary="Mark a single message as read",
        responses={200: openapi.Response("Message marked as read")},
        tags=["messages"]
    )
    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read_single(self, request: Request, pk=None):
        try:
            logger.debug(f"mark_read_single called for message {pk}")
            message = self.get_object()

            if message.sender == request.user:
                logger.warning(f"User {request.user.id} attempted to mark own message {pk} as read")
                return Response(
                    {"detail": "Cannot mark your own message as read"},
                    status=HTTP_400_BAD_REQUEST,
                )

            if not message.conversation.participants.filter(user=request.user).exists():
                logger.warning(
                    f"User {request.user.id} is not a participant in conversation {message.conversation.id}"
                )
                return Response(
                    {"detail": "You are not a participant in this conversation"},
                    status=HTTP_403_FORBIDDEN,
                )

            status_obj, created = MessageReadStatus.objects.get_or_create(
                message=message, user=request.user, defaults={"read_at": timezone.now()}
            )

            if created:
                message.mark_as_read(request.user)
                logger.info(f"Marked message {message.id} as read for user {request.user.id}")

            return Response(
                {
                    "detail": "Message marked as read",
                    "message_id": message.id,
                    "was_new": created,
                }
            )
        except Exception as e:
            logger.error(f"Error in mark_read_single: {str(e)}", exc_info=True)
            return Response(
                {"detail": f"Error marking message as read: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        operation_summary="Reply to a message",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["content"],
            properties={
                "content": openapi.Schema(type=openapi.TYPE_STRING, description="Reply content"),
            },
        ),
        responses={201: MessageSerializer},
        tags=["messages"]
    )
    @action(detail=True, methods=["post"], url_path="reply")
    def create_reply(self, request: Request, pk=None):
        try:
            logger.debug(f"create_reply called for message {pk}")
            message = self.get_object()
            conversation = message.conversation

            if not conversation.participants.filter(user=request.user).exists():
                logger.warning(
                    f"User {request.user.id} is not a participant in conversation {conversation.id}"
                )
                return Response(
                    {"detail": "You are not a participant in this conversation"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            content = request.data.get("content", "").strip()
            if not content:
                logger.warning("Reply content is required")
                return Response(
                    {"detail": "Reply content is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            reply_data = {
                "type": "text",
                "content": content,
                "reply_to": message.id,
                "conversation": conversation.id,
            }

            logger.debug(f"Creating reply: {reply_data}")

            context = {"request": request}
            serializer = MessageSerializer(data=reply_data, context=context)

            if serializer.is_valid():
                result = serializer.save()
                logger.info(f"Reply created successfully: {result['id']}")
                return Response(result, status=status.HTTP_201_CREATED)
            else:
                logger.error(f"Reply serializer errors: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Error in create_reply: {str(e)}", exc_info=True)
            return Response(
                {"detail": f"Error sending reply: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )