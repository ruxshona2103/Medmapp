import logging
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

logger = logging.getLogger(__name__)

User = get_user_model()

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


# ===========================================================
# Conversation (suhbat) ViewSet
# ===========================================================
class ConversationViewSet(viewsets.ModelViewSet):
    queryset = (
        Conversation.objects
        .select_related("patient", "operator", "created_by")
        .prefetch_related("participants")
    )
    serializer_class = ConversationSerializer
    pagination_class = StandardResultsSetPagination
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_permissions(self):
        if self.action in [
            "conversation_messages",
            "mark_read",
            "get_prescriptions",
            "get_summary",
            "get_files",
            "operator_mark_read",
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
                Q(participants__user=user) | Q(created_by=user),
                is_active=True,
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
            if hasattr(Conversation, "status"):
                qs = qs.filter(status=mapped_status)
                logger.debug(f"Filtering conversations by status: {mapped_status}")
            else:
                # Modelda status bo'lmasa – taxminiy filter
                if mapped_status == "new":
                    # o'qilmagan xabarlari bor
                    qs = qs.filter(messages__read_status__isnull=True).exclude(messages__sender=user).distinct()
                elif mapped_status == "in_progress":
                    # oxirgi 24 soatda yozilgan
                    qs = qs.filter(last_message_at__gte=timezone.now() - timezone.timedelta(days=1))
                elif mapped_status == "completed":
                    # hammasi o'qilgan
                    qs = qs.filter(
                        ~Q(messages__read_status__isnull=True) | Q(messages__sender=user)
                    ).distinct()

        return qs.order_by("-last_message_at")

    def get_object(self):
        try:
            logger.debug(f"Attempting to get conversation with pk={self.kwargs['pk']}")
            obj = Conversation.objects.get(pk=self.kwargs["pk"], is_active=True)
            self.check_object_permissions(self.request, obj)
            logger.debug(f"Found conversation: {obj.id}")
            return obj
        except Conversation.MultipleObjectsReturned:
            logger.warning(f"Multiple active conversations found for pk={self.kwargs['pk']}")
            obj = (
                Conversation.objects.filter(pk=self.kwargs["pk"], is_active=True)
                .order_by("-last_message_at")
                .first()
            )
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
            openapi.Parameter(
                "page",
                openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                description="Sahifa raqami",
            ),
            openapi.Parameter(
                "page_size",
                openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                description="Sahifadagi elementlar soni (max 100)",
            ),
        ],
        responses={200: ConversationSerializer(many=True)},
        tags=["conversations"],
    )
    def list(self, request, *args, **kwargs):
        try:
            logger.debug(f"Listing conversations for user {request.user.id}")
            queryset = self.get_queryset()

            # pagination
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

    # -------------------------------------------------------
    # CREATE
    # -------------------------------------------------------
    @swagger_auto_schema(
        operation_summary="➕ Yangi suhbat yaratish",
        operation_description="Yangi suhbat yaratish (operator bemor bilan, yoki foydalanuvchi support bilan)",
        request_body=ConversationCreateSerializer,
        responses={
            201: ConversationSerializer,
            400: "Bad request - Validation error",
            500: "Internal server error"
        },
        tags=["conversations"],
    )
    def create(self, request, *args, **kwargs):
        """
        Yangi suhbat yaratish.
        Odatda operator bemor bilan, yoki foydalanuvchi support bilan.
        """
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

    # -------------------------------------------------------
    # PRIVATE helper – GET messages
    # -------------------------------------------------------
    def _get_messages(self, conversation, request, context):
        """
        Ichki funksiya.
        Bitta suhbatdagi xabarlarni qaytaradi.
        Faqat suhbat ishtirokchilari ko'ra oladi.
        """
        try:
            logger.debug(f"Getting messages for conversation {conversation.id}, user {request.user.id}")

            # ruxsat
            if not conversation.participants.filter(user=request.user).exists():
                logger.warning(
                    f"User {request.user.id} is not a participant in conversation {conversation.id}"
                )
                return Response(
                    {"detail": "You are not a participant in this conversation"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # xabarlarni olish
            queryset = (
                conversation.messages.select_related("sender", "reply_to__sender")
                .prefetch_related("attachments__uploaded_by")
                .filter(is_deleted=False)
                .order_by("id")
            )

            # faqat yangi xabarlar
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

    # -------------------------------------------------------
    # PRIVATE helper – POST message
    # -------------------------------------------------------
    def _post_message(self, conversation, request, context):
        """
        Ichki funksiya.
        Bitta suhbatga yangi xabar yuboradi.
        """
        try:
            logger.debug(f"Posting message to conversation {conversation.id}")

            # ruxsat
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
        elif request.method == "POST":
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

            # o'zi yozmagan va hali o'qilmagan xabarlar
            unread_messages = (
                conversation.messages.exclude(sender=request.user)
                .exclude(read_status__user=request.user)
                .filter(is_deleted=False)
            )

            marked_count = 0
            for message in unread_messages:
                MessageReadStatus.objects.get_or_create(
                    message=message,
                    user=request.user,
                    defaults={"read_at": timezone.now()},
                )
                message.mark_as_read(request.user)
                marked_count += 1

            logger.info(f"Marked {marked_count} messages as read in conversation {conversation.id}")
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

    # -------------------------------------------------------
    # GET /conversations/my/
    # Authenticated user o‘ziga tegishli conversationlarni oladi
    # -------------------------------------------------------
    @swagger_auto_schema(
        operation_summary="🧑‍💻 Foydalanuvchining suhbatlari",
        operation_description=(
                "JWT token orqali login qilingan foydalanuvchi o‘z ishtirok etgan "
                "barcha suhbatlarni ko‘radi (Conversation list)."
        ),
        manual_parameters=[
            openapi.Parameter(
                "page",
                openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                description="Sahifa raqami",
            ),
            openapi.Parameter(
                "page_size",
                openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                description="Sahifadagi elementlar soni (max 100)",
            ),
        ],
        responses={200: ConversationSerializer(many=True)},
        tags=["conversations"],
    )
    @action(detail=False, methods=["get"], url_path="my")
    def my_conversations(self, request):
        user = request.user

        # ✅ Auth required
        if not user.is_authenticated:
            return Response(
                {"detail": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # ✅ Faqat o‘zi ishtirok etgan conversation lar
        qs = (
            Conversation.objects.filter(
                participants__user=user,
                is_active=True
            )
            .distinct()
            .select_related("patient", "operator", "created_by")
            .prefetch_related("participants")
            .order_by("-last_message_at")
        )

        # ✅ Pagination
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = ConversationSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)

        serializer = ConversationSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

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
            serializer = PrescriptionSerializer(prescriptions, many=True, context={"request": request})
            logger.info(f"Retrieved {prescriptions.count()} prescriptions for conversation {conversation.id}")
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error in get_prescriptions: {str(e)}", exc_info=True)
            return Response(
                {"detail": f"Error retrieving prescriptions: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

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

    # -------------------------------------------------------
    # GET/POST /conversations/{id}/files/
    # -------------------------------------------------------
    @swagger_auto_schema(
        methods=['get'],
        operation_summary="📁 Suhbatdagi fayllar ro'yxati",
        operation_description="Tanlangan suhbatga yuklangan barcha fayllarni qaytaradi.",
        responses={
            200: openapi.Response(
                description="List of attachments",
                schema=AttachmentSerializer(many=True)
            ),
            403: "Forbidden - Not a participant"
        },
        tags=["conversations"],
    )
    @swagger_auto_schema(
        methods=['post'],
        operation_summary="📤 Suhbatga fayl yuklash",
        operation_description="Bir yoki bir nechta faylni suhbatga yuklaydi. Content maydoni ixtiyoriy.",
        consumes=['multipart/form-data'],
        manual_parameters=[
            openapi.Parameter(
                'files',
                openapi.IN_FORM,
                description="Yuklanadigan fayllar (bir nechta fayl yuklash mumkin)",
                type=openapi.TYPE_FILE,
                required=True
            ),
            openapi.Parameter(
                'content',
                openapi.IN_FORM,
                description="Fayl uchun ixtiyoriy xabar matni",
                type=openapi.TYPE_STRING,
                required=False
            ),
        ],
        responses={
            201: openapi.Response(
                description="Fayllar muvaffaqiyatli yuklandi",
                schema=MessageSerializer
            ),
            400: "Bad request - Fayl yuborilmadi",
            403: "Forbidden - Siz bu suhbat ishtirokchisi emassiz",
            500: "Internal server error"
        },
        tags=["conversations"],
    )
    @action(
        detail=True,
        methods=["get", "post"],
        url_path="files",
        parser_classes=[MultiPartParser, FormParser]
    )
    def get_files(self, request, pk=None):
        try:
            conversation = self.get_object()

            # Ruxsat tekshirish
            if not conversation.participants.filter(user=request.user).exists():
                logger.warning(
                    f"User {request.user.id} is not a participant in conversation {conversation.id}"
                )
                return Response(
                    {"detail": "You are not a participant in this conversation"},
                    status=HTTP_403_FORBIDDEN,
                )

            if request.method == "GET":
                logger.debug(f"get_files called for conversation {conversation.id}")
                attachments = (
                    Attachment.objects.filter(
                        message__conversation=conversation,
                        message__is_deleted=False,
                    )
                    .select_related("message", "uploaded_by")
                    .order_by("-created_at")
                )

                serializer = AttachmentSerializer(attachments, many=True, context={"request": request})
                logger.info(f"Retrieved {attachments.count()} files for conversation {conversation.id}")
                return Response(serializer.data)

            elif request.method == "POST":
                logger.debug(f"post_files called for conversation {conversation.id}")

                files = request.FILES.getlist("files", [])
                if not files:
                    logger.warning("No files provided")
                    return Response(
                        {"detail": "Kamida bitta fayl yuborish kerak"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                content = request.data.get("content", "").strip()

                # Fayl xabar yaratamiz
                data = {
                    "conversation": conversation.id,
                    "type": "file",
                    "content": content or "Fayl yuborildi",
                }

                # MessageSerializer orqali xabar yaratamiz
                context = {"request": request}
                serializer = MessageSerializer(data=data, context=context)

                if serializer.is_valid():
                    result = serializer.save()
                    logger.info(f"File message created in conversation {conversation.id}")
                    return Response(result, status=status.HTTP_201_CREATED)
                else:
                    logger.error(f"File message serializer errors: {serializer.errors}")
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Error in get_files: {str(e)}", exc_info=True)
            return Response(
                {"detail": f"Error with files: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # -------------------------------------------------------
    # POST /conversations/{id}/operator-mark-read/
    # (faqat operator uchun)
    # -------------------------------------------------------
    @swagger_auto_schema(
        operation_summary="✅ Operator xabarlarni o'qilgan qiladi",
        operation_description="Operator sifatida shu suhbatdagi o'qilmagan xabarlarni o'qilgan qilib belgilaydi.",
        responses={200: openapi.Response("Messages marked as read by operator")},
        tags=["conversations"],
    )
    @action(detail=True, methods=["post"], url_path="operator-mark-read")
    def operator_mark_read(self, request, pk=None):
        try:
            conversation = self.get_object()
            logger.debug(f"operator_mark_read called for conversation {conversation.id}")

            # faqat operator / staff
            if not request.user.is_staff and not hasattr(request.user, "is_operator"):
                logger.warning(f"User {request.user.id} is not authorized for operator actions")
                return Response(
                    {"detail": "Only operators can perform this action"},
                    status=HTTP_403_FORBIDDEN,
                )

            unread_messages = (
                conversation.messages.exclude(sender=request.user)
                .exclude(read_status__user=request.user)
                .filter(is_deleted=False)
            )

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



# ===========================================================
# Message ViewSet – alohida xabar bilan ishlash
# ===========================================================
class MessageViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Xabarlarni boshqarish uchun ViewSet.

    Nimalarni qiladi:
    - retrieve (GET /messages/{id}/) – bitta xabarni olish
    - update/partial_update – xabarni tahrirlash (o‘zi yozgan bo‘lsa)
    - delete – xabarni o‘chirish (aslida soft-delete)
    - mark-read – xabarni o‘qilgan deb belgilash
    - reply – shu xabarga javob yozish
    """

    queryset = (
        Message.objects
        .select_related("conversation", "sender", "reply_to")
        .prefetch_related("attachments")
    )
    serializer_class = MessageSerializer
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    pagination_class = StandardResultsSetPagination

    def get_permissions(self):
        """
        Ba’zi actionlar faqat login qilganlar uchun.
        """
        if self.action in ["mark_read_single", "create_reply"]:
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        """
        Foydalanuvchi faqat o‘zi qatnashayotgan suhbatlardagi xabarlarni ko‘ra oladi.
        """
        user = self.request.user
        if not user.is_authenticated:
            logger.debug("User is not authenticated, returning empty queryset")
            return Message.objects.none()

        logger.debug(f"Fetching messages for user {user.id}")
        return (
            self.queryset.filter(
                conversation__participants__user=user,
                is_deleted=False,
            )
            .order_by("id")
        )

    def perform_update(self, serializer):
        """
        Xabarni tahrirlashda edited_at maydonini yangilab qo‘yish.
        """
        instance = serializer.save()
        instance.edited_at = timezone.now()
        instance.save(update_fields=["edited_at"])
        logger.info(f"Message {instance.id} updated by user {self.request.user.id}")

    def perform_destroy(self, instance):
        """
        Xabarni o‘chirish – logikaviy o‘chirish.
        Faqat o‘zi yozgan xabarini o‘chirishi mumkin.
        """
        if instance.sender != self.request.user:
            logger.warning(
                f"User {self.request.user.id} attempted to delete message {instance.id} not owned by them"
            )
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
        try:
            logger.debug(f"mark_read_single called for message {pk}")
            message = self.get_object()

            # o‘zi yozgan xabarini o‘qilgan deb belgilashga hojat yo‘q
            if message.sender == request.user:
                logger.warning(f"User {request.user.id} attempted to mark own message {pk} as read")
                return Response(
                    {"detail": "Cannot mark your own message as read"},
                    status=HTTP_400_BAD_REQUEST,
                )

            # suhbat ishtirokchisi bo‘lishi kerak
            if not message.conversation.participants.filter(user=request.user).exists():
                logger.warning(
                    f"User {request.user.id} is not a participant in conversation {message.conversation.id}"
                )
                return Response(
                    {"detail": "You are not a participant in this conversation"},
                    status=HTTP_403_FORBIDDEN,
                )

            status_obj, created = MessageReadStatus.objects.get_or_create(
                message=message,
                user=request.user,
                defaults={"read_at": timezone.now()},
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

    # -------------------------------------------------------
    # POST /messages/{id}/reply/
    # -------------------------------------------------------
    @swagger_auto_schema(
        operation_summary="↩️ Xabarga javob yozish",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["content"],
            properties={
                "content": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Javob matni",
                ),
            },
        ),
        responses={201: MessageSerializer},
        tags=["messages"],
    )
    @action(detail=True, methods=["post"], url_path="reply")
    def create_reply(self, request: Request, pk=None):
        try:
            logger.debug(f"create_reply called for message {pk}")
            message = self.get_object()
            conversation = message.conversation

            # ruxsat
            if not conversation.participants.filter(user=request.user).exists():
                logger.warning(
                    f"User {request.user.id} is not a participant in conversation {conversation.id}"
                )
                return Response(
                    {"detail": "You are not a participant in this conversation"},
                    status=HTTP_403_FORBIDDEN,
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
