# views.py
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

User = get_user_model()


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class ConversationViewSet(viewsets.ModelViewSet):
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
            return Conversation.objects.none()

        is_operator = user.is_staff or getattr(user, "role", None) == "operator"

        if is_operator:
            return (
                Conversation.objects.filter(
                    Q(operator=user) | Q(created_by=user), is_active=True
                )
                .select_related("patient", "operator")
                .prefetch_related("participants")
                .order_by("-last_message_at")
            )
        else:
            # Bemor uchun - o'z suhbatlarini ko'rish
            return (
                Conversation.objects.filter(
                    Q(patient=user) | Q(participants__user=user), is_active=True
                )
                .select_related("patient", "operator")
                .prefetch_related("participants")
                .distinct()
                .order_by("-last_message_at")
            )

    def get_serializer_class(self):
        if self.action == "create":
            return ConversationCreateSerializer
        return super().get_serializer_class()

    def create(self, request: Request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            conversation = serializer.save()
            print(f"Created conversation {conversation.id} for user {request.user.id}")
            return Response(
                ConversationSerializer(conversation, context={"request": request}).data,
                status=status.HTTP_201_CREATED,
            )
        except DRFValidationError as e:
            print(f"Validation error: {e.detail}")
            return Response(
                {"detail": str(e.detail) if hasattr(e, "detail") else str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            print(f"Create conversation error: {str(e)}")
            import traceback

            traceback.print_exc()
            return Response(
                {"detail": f"Error creating conversation: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _get_messages(self, conversation, request, context):
        try:
            print(
                f"Getting messages for conversation {conversation.id}, user {request.user.id}"
            )

            # Permission check
            if not conversation.participants.filter(user=request.user).exists():
                print(
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
                    print(f"Filtering messages after ID {since_id}")
                except (ValueError, TypeError):
                    print(f"Invalid since_id: {since_id}")

            search_query = request.query_params.get("q")
            if search_query:
                print(f"Searching for: {search_query}")
                queryset = queryset.filter(
                    Q(content__icontains=search_query)
                    | Q(attachments__original_name__icontains=search_query)
                ).distinct()

            message_count = queryset.count()
            print(f"Found {message_count} messages")

            page = self.paginate_queryset(queryset)
            if page is not None:
                messages_data = MessageSerializer(page, many=True, context=context).data
                paginated_response = self.get_paginated_response(messages_data).data
                return Response(
                    {
                        "conversation": ConversationSerializer(
                            conversation, context=context
                        ).data,
                        "results": messages_data,
                        "pagination": paginated_response,
                    }
                )

            messages_data = MessageSerializer(queryset, many=True, context=context).data
            return Response(
                {
                    "conversation": ConversationSerializer(
                        conversation, context=context
                    ).data,
                    "results": messages_data,
                    "count": message_count,
                }
            )
        except Exception as e:
            print(f"Error in _get_messages: {str(e)}")
            import traceback

            traceback.print_exc()
            return Response(
                {"detail": f"Error retrieving messages: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _post_message(self, conversation, request, context):
        try:
            print(
                f"Posting message to conversation {conversation.id}, user {request.user.id}"
            )

            # Permission check
            if not conversation.participants.filter(user=request.user).exists():
                print(
                    f"User {request.user.id} is not a participant in conversation {conversation.id}"
                )
                return Response(
                    {"detail": "You are not a participant in this conversation"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            files = request.FILES.getlist("attachments") if request.FILES else []
            print(f"Files count: {len(files)}")

            data = {
                "conversation": conversation.id,
                "type": request.data.get("type", "text" if not files else "file"),
                "content": request.data.get("content", "").strip(),
                "reply_to": request.data.get("reply_to"),
            }

            print(f"Message data: {data}")

            if data["type"] == "text" and not data["content"]:
                return Response(
                    {"detail": "Content is required for text messages"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if data["type"] == "file" and not files:
                return Response(
                    {"detail": "At least one file is required for file messages"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # File size validation
            for file in files:
                if hasattr(file, "size") and file.size > 10 * 1024 * 1024:
                    return Response(
                        {"detail": f'File "{file.name}" exceeds 10MB limit'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            context["conversation"] = conversation

            serializer = MessageSerializer(data=data, context=context)
            if serializer.is_valid():
                print("Serializer valid, saving message...")
                result = serializer.save()
                print(f"Message saved successfully: {result['id']}")
                return Response(result, status=status.HTTP_201_CREATED)
            else:
                print(f"Serializer errors: {serializer.errors}")
                error_detail = {
                    field: (
                        [str(error) for error in errors]
                        if isinstance(errors, list)
                        else str(errors)
                    )
                    for field, errors in serializer.errors.items()
                }
                return Response(
                    {"detail": error_detail}, status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            print(f"Error in _post_message: {str(e)}")
            import traceback

            traceback.print_exc()
            return Response(
                {"detail": f"Error sending message: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        operation_summary="Retrieve conversation messages",
        operation_description="Retrieve all messages in a specified conversation",
        manual_parameters=[
            openapi.Parameter(
                name="since_id",
                in_=openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                description="Messages after the specified message ID",
                required=False,
            ),
            openapi.Parameter(
                name="q",
                in_=openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Search messages",
                required=False,
            ),
        ],
        responses={
            200: openapi.Response("List of messages", MessageSerializer(many=True))
        },
    )
    @action(detail=True, methods=["get"], url_path="messages")
    def get_messages(self, request: Request, pk=None):
        try:
            print(f"get_messages called for conversation {pk}, user {request.user.id}")
            conversation = self.get_object()
            context = {"request": request}
            return self._get_messages(conversation, request, context)
        except Conversation.DoesNotExist:
            print(f"Conversation {pk} not found")
            return Response(
                {"detail": "Conversation not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"Error in get_messages: {str(e)}")
            import traceback

            traceback.print_exc()
            return Response(
                {"detail": f"Error retrieving messages: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        operation_summary="Send a new message",
        operation_description="Send a new message to a specified conversation",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "type": openapi.Schema(
                    type=openapi.TYPE_STRING, enum=["text", "file"], default="text"
                ),
                "content": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Message content"
                ),
                "reply_to": openapi.Schema(type=openapi.TYPE_INTEGER, nullable=True),
            },
            required=["content"],
        ),
        responses={201: MessageSerializer},
    )
    @action(detail=True, methods=["post"], url_path="messages")
    def post_message(self, request: Request, pk=None):
        try:
            print(f"post_message called for conversation {pk}, user {request.user.id}")
            conversation = self.get_object()
            context = {"request": request}
            return self._post_message(conversation, request, context)
        except Conversation.DoesNotExist:
            print(f"Conversation {pk} not found")
            return Response(
                {"detail": "Conversation not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"Error in post_message: {str(e)}")
            import traceback

            traceback.print_exc()
            return Response(
                {"detail": f"Error sending message: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        operation_summary="Mark messages as read",
        operation_description="Mark all or specified messages in a conversation as read",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "message_ids": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_INTEGER),
                    description="Specific message IDs (optional)",
                )
            },
        ),
        responses={200: "Success"},
    )
    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request: Request, pk=None):
        try:
            print(f"mark_read called for conversation {pk}, user {request.user.id}")
            conversation = self.get_object()

            if not conversation.participants.filter(user=request.user).exists():
                return Response(
                    {"detail": "You are not a participant in this conversation"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            message_ids = request.data.get("message_ids", [])
            messages = conversation.messages.filter(is_deleted=False).exclude(
                sender=request.user
            )
            if message_ids:
                messages = messages.filter(id__in=message_ids)

            print(f"Marking {messages.count()} messages as read")

            updated_count = 0
            for message in messages:
                status_obj, created = MessageReadStatus.objects.get_or_create(
                    message=message,
                    user=request.user,
                    defaults={"read_at": timezone.now()},
                )
                if created:
                    message.mark_as_read(request.user)
                    updated_count += 1

            if not message_ids:
                last_message = messages.order_by("-id").first()
                if (
                    last_message
                    and not MessageReadStatus.objects.filter(
                        message=last_message, user=request.user
                    ).exists()
                ):
                    MessageReadStatus.objects.create(
                        message=last_message, user=request.user, read_at=timezone.now()
                    )
                    last_message.mark_as_read(request.user)
                    updated_count += 1

            print(f"Updated {updated_count} message read statuses")
            return Response(
                {
                    "detail": f"{updated_count} messages marked as read",
                    "updated_count": updated_count,
                    "total_messages": messages.count(),
                }
            )
        except Exception as e:
            print(f"Error in mark_read: {str(e)}")
            return Response(
                {"detail": f"Error marking messages as read: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        operation_summary="Retrieve prescriptions",
        operation_description="Retrieve prescriptions for a specified conversation",
        responses={
            200: openapi.Response(
                "List of prescriptions", PrescriptionSerializer(many=True)
            )
        },
    )
    @action(detail=True, methods=["get"], url_path="prescriptions")
    def get_prescriptions(self, request: Request, pk=None):
        try:
            print(f"Getting prescriptions for conversation {pk}")
            conversation = self.get_object()
            if not conversation.participants.filter(user=request.user).exists():
                return Response(
                    {"detail": "You are not a participant in this conversation"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            prescriptions = conversation.prescriptions.all()
            serializer = PrescriptionSerializer(
                prescriptions, many=True, context={"request": request}
            )
            return Response(serializer.data)
        except Conversation.DoesNotExist:
            return Response(
                {"detail": "Conversation not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"Error in get_prescriptions: {str(e)}")
            return Response(
                {"detail": f"Error retrieving prescriptions: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        operation_summary="Retrieve conversation summary",
        operation_description="Retrieve the summary or details for a specified conversation",
        responses={200: DoctorSummarySerializer, 404: "No summary found"},
    )
    @action(detail=True, methods=["get"], url_path="summary")
    def get_summary(self, request: Request, pk=None):
        try:
            print(f"Getting summary for conversation {pk}")
            conversation = self.get_object()
            if not conversation.participants.filter(user=request.user).exists():
                return Response(
                    {"detail": "You are not a participant in this conversation"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Operator uchun maxsus xulosa
            if conversation.operator and conversation.operator == request.user:
                summary_data = {
                    "conversation_id": conversation.id,
                    "title": conversation.title,
                    "patient": UserTinySerializer(
                        conversation.patient, context={"request": request}
                    ).data,
                    "operator": UserTinySerializer(
                        conversation.operator, context={"request": request}
                    ).data,
                    "last_message_at": conversation.last_message_at,
                    "unread_count": conversation.messages.filter(
                        sender=conversation.patient, is_deleted=False
                    )
                    .exclude(read_statuses__user=request.user)
                    .count(),
                    "message_count": conversation.messages.filter(
                        is_deleted=False
                    ).count(),
                }
                return Response(summary_data)

            # Bemor yoki boshqa holatlar uchun DoctorSummary
            try:
                summary = conversation.doctor_summary
            except DoctorSummary.DoesNotExist:
                return Response(
                    {"detail": "No summary found for this conversation"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = DoctorSummarySerializer(summary, context={"request": request})
            return Response(serializer.data)

        except Conversation.DoesNotExist:
            return Response(
                {"detail": "Conversation not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"Error in get_summary: {str(e)}")
            return Response(
                {"detail": f"Error retrieving summary: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        operation_summary="Retrieve files",
        operation_description="Retrieve files attached to a specified conversation",
        responses={
            200: openapi.Response("List of files", AttachmentSerializer(many=True))
        },
    )
    @action(detail=True, methods=["get"], url_path="files")
    def get_files(self, request: Request, pk=None):
        try:
            print(f"Getting files for conversation {pk}")
            conversation = self.get_object()
            if not conversation.participants.filter(user=request.user).exists():
                return Response(
                    {"detail": "You are not a participant in this conversation"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            files = Attachment.objects.filter(message__conversation=conversation)
            serializer = AttachmentSerializer(
                files, many=True, context={"request": request}
            )
            return Response(serializer.data)
        except Conversation.DoesNotExist:
            return Response(
                {"detail": "Conversation not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"Error in get_files: {str(e)}")
            return Response(
                {"detail": f"Error retrieving files: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        operation_summary="Operator mark messages as read",
        operation_description="Mark messages in a patient conversation as read by operator",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "message_ids": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_INTEGER),
                    description="Specific message IDs (optional)",
                )
            },
        ),
        responses={200: "Success"},
    )
    @action(detail=True, methods=["post"], url_path="operator/mark-read")
    def operator_mark_read(self, request: Request, pk=None):
        try:
            print(f"operator_mark_read called for conversation {pk}")
            return self.mark_read(request, pk)
        except Exception as e:
            print(f"Error in operator_mark_read: {str(e)}")
            return Response(
                {"detail": f"Error marking messages as read: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        methods=["GET"],
        operation_summary="Retrieve operator conversation messages",
        operation_description="Retrieve messages in a conversation with a patient by operator",
        manual_parameters=[
            openapi.Parameter(
                name="patient_id",
                in_=openapi.IN_PATH,
                type=openapi.TYPE_INTEGER,
                description="Patient ID",
                required=True,
            ),
            openapi.Parameter(
                name="since_id",
                in_=openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                description="Messages after the specified message ID",
                required=False,
            ),
        ],
        responses={
            200: openapi.Response("List of messages", MessageSerializer(many=True)),
            403: "Not an operator",
            404: "Patient not found",
        },
    )
    @swagger_auto_schema(
        methods=["POST"],
        operation_summary="Send message in operator conversation",
        operation_description="Send a new message in a conversation with a patient by operator",
        manual_parameters=[
            openapi.Parameter(
                name="patient_id",
                in_=openapi.IN_PATH,
                type=openapi.TYPE_INTEGER,
                description="Patient ID",
                required=True,
            ),
        ],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "type": openapi.Schema(
                    type=openapi.TYPE_STRING, enum=["text", "file"], default="text"
                ),
                "content": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Message content"
                ),
                "reply_to": openapi.Schema(type=openapi.TYPE_INTEGER, nullable=True),
            },
            required=["content"],
        ),
        responses={
            201: MessageSerializer,
            403: "Not an operator",
            404: "Patient not found",
        },
    )
    @action(
        detail=False,
        methods=["get", "post"],
        url_path=r"operator/(?P<patient_id>\d+)/messages",
    )
    def operator_conversation_messages(self, request: Request, patient_id=None):
        try:
            print(f"Operator conversation messages called, patient_id: {patient_id}")

            # Validate patient_id
            try:
                patient_id = int(patient_id)
            except (ValueError, TypeError):
                return Response(
                    {"detail": "Invalid patient ID format"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check if user is operator
            if not (
                request.user.is_authenticated
                and (
                    request.user.is_staff
                    or getattr(request.user, "role", None) == "operator"
                )
            ):
                print(f"User {request.user.id} is not authorized as operator")
                return Response(
                    {"detail": "Only operators can use this endpoint"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            patient = get_object_or_404(User, pk=patient_id)
            print(f"Found patient: {patient.get_full_name()}")

            # Get or create conversation
            conversation, created = Conversation.objects.get_or_create(
                patient=patient,
                operator=request.user,
                defaults={
                    "created_by": request.user,
                    "title": f"Operator conversation: {patient.get_full_name() or patient.username or f'User {patient_id}'}",
                    "last_message_at": timezone.now(),
                },
            )

            print(f"Conversation {conversation.id}, created: {created}")

            if created:
                print("Creating participants and welcome message")
                Participant.objects.get_or_create(
                    conversation=conversation,
                    user=patient,
                    defaults={"role": "patient"},
                )
                Participant.objects.get_or_create(
                    conversation=conversation,
                    user=request.user,
                    defaults={"role": "operator"},
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

            context = {"request": request}

            if request.method == "GET":
                return self._get_messages(conversation, request, context)
            elif request.method == "POST":
                return self._post_message(conversation, request, context)

        except Exception as e:
            print(f"Error in operator_conversation_messages: {str(e)}")
            import traceback

            traceback.print_exc()
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
            return Message.objects.none()

        return self.queryset.filter(
            conversation__participants__user=user, is_deleted=False
        ).order_by("id")

    def perform_update(self, serializer):
        instance = serializer.save()
        instance.edited_at = timezone.now()
        instance.save(update_fields=["edited_at"])

    def perform_destroy(self, instance):
        if instance.sender != self.request.user:
            raise PermissionDenied("You can only delete your own messages")
        instance.soft_delete()

    @swagger_auto_schema(operation_summary="Mark a single message as read")
    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read_single(self, request: Request, pk=None):
        try:
            print(f"mark_read_single called for message {pk}")
            message = self.get_object()

            if message.sender == request.user:
                return Response(
                    {"detail": "Cannot mark your own message as read"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not message.conversation.participants.filter(user=request.user).exists():
                return Response(
                    {"detail": "You are not a participant in this conversation"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            status, created = MessageReadStatus.objects.get_or_create(
                message=message, user=request.user, defaults={"read_at": timezone.now()}
            )

            if created:
                message.mark_as_read(request.user)
                print(f"Marked message {message.id} as read for user {request.user.id}")

            return Response(
                {
                    "detail": "Message marked as read",
                    "message_id": message.id,
                    "was_new": created,
                }
            )
        except Exception as e:
            print(f"Error in mark_read_single: {str(e)}")
            return Response(
                {"detail": f"Error marking message as read: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(operation_summary="Reply to a message")
    @action(detail=True, methods=["post"], url_path="reply")
    def create_reply(self, request: Request, pk=None):
        try:
            print(f"create_reply called for message {pk}")
            message = self.get_object()
            conversation = message.conversation

            if not conversation.participants.filter(user=request.user).exists():
                return Response(
                    {"detail": "You are not a participant in this conversation"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            content = request.data.get("content", "").strip()
            if not content:
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

            print(f"Creating reply: {reply_data}")

            context = {"request": request}
            serializer = MessageSerializer(data=reply_data, context=context)

            if serializer.is_valid():
                result = serializer.save()
                print(f"Reply created successfully: {result['id']}")
                return Response(result, status=status.HTTP_201_CREATED)
            else:
                print(f"Reply serializer errors: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            print(f"Error in create_reply: {str(e)}")
            return Response(
                {"detail": f"Error sending reply: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
