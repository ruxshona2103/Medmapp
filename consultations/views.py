from django.db.models import Q
from django.http import QueryDict
from django.utils import timezone

from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser

from .models import (
    Conversation, Message, Attachment, ReadReceipt,
    DoctorSummary, Prescription
)
from .serializers import (
    ConversationSerializer, ConversationCreateSerializer,
    MessageSerializer, AttachmentSerializer,
    DoctorSummarySerializer, PrescriptionSerializer
)
from .permissions import (
    IsConversationParticipant, IsMessageOwnerOrReadOnly, IsDoctorParticipant
)


# consultations/views.py
from django.http import QueryDict
from django.utils import timezone
from django.db.models import Q

from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Conversation, Message, Attachment, ReadReceipt, DoctorSummary, Prescription
from .serializers import (
    ConversationSerializer, ConversationCreateSerializer,
    MessageSerializer, AttachmentSerializer,
    DoctorSummarySerializer, PrescriptionSerializer
)
from .permissions import IsConversationParticipant, IsMessageOwnerOrReadOnly, IsDoctorParticipant


class ConversationViewSet(viewsets.ModelViewSet):
    queryset = Conversation.objects.all().select_related("patient", "doctor")
    serializer_class = ConversationSerializer
    permission_classes = [IsConversationParticipant]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_queryset(self):
        u = self.request.user
        return (Conversation.objects
                .filter(participants__user=u, is_active=True)
                .distinct()
                .select_related("patient", "doctor"))

    def get_serializer_class(self):
        return ConversationCreateSerializer if self.action == "create" else ConversationSerializer

    # ---- Swagger uchun messages POST body'ni qo'lda ta'riflaymiz (yangi serializer yaratmaymiz!)
    message_body = openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "type": openapi.Schema(type=openapi.TYPE_STRING, enum=["text", "file"], default="text"),
            "content": openapi.Schema(type=openapi.TYPE_STRING, description="Matn xabar"),
            "reply_to": openapi.Schema(type=openapi.TYPE_INTEGER, nullable=True),
            "attachments": openapi.Schema(  # multipart/form-data
                type=openapi.TYPE_ARRAY,
                items=openapi.Items(type=openapi.TYPE_STRING, format="binary"),
                description="Fayllar ro'yxati (type=file bo'lsa)"
            ),
        },
        required=[],
    )

    @swagger_auto_schema(method="get", responses={200: MessageSerializer(many=True)})
    @swagger_auto_schema(method="post", request_body=message_body, responses={201: MessageSerializer})
    @action(detail=True, methods=["get", "post"], url_path="messages",
            parser_classes=[JSONParser, FormParser, MultiPartParser])
    def messages(self, request, pk=None):
        conv = self.get_object()

        # ---------- GET: xabarlar ro'yxati ----------
        if request.method.lower() == "get":
            qs = (conv.messages
                  .select_related("sender")
                  .prefetch_related("attachments")
                  .order_by("id"))

            since_id = request.query_params.get("since_id")
            if since_id:
                try:
                    qs = qs.filter(id__gt=int(since_id))
                except (TypeError, ValueError):
                    pass

            q = request.query_params.get("q")
            if q:
                qs = qs.filter(content__icontains=q)

            page = self.paginate_queryset(qs)
            if page is not None:
                return self.get_paginated_response(
                    MessageSerializer(page, many=True, context={"request": request}).data
                )
            return Response(MessageSerializer(qs, many=True, context={"request": request}).data)

        # ---------- POST: xabar yuborish (JSON yoki multipart) ----------
        payload = request.data.copy() if isinstance(request.data, QueryDict) else request.data
        files = request.FILES.getlist("attachments")

        msg_type = payload.get("type") or ("file" if files else "text")
        content = payload.get("content", "")

        # Minimal tekshiruv (aniq xabar turi bo'yicha)
        if msg_type == "text" and not content:
            return Response({"content": "Matn bo'sh bo'lmasin."}, status=400)
        if msg_type == "file" and not files:
            return Response({"attachments": "Kamida bitta fayl biriktiring."}, status=400)

        data = {"type": msg_type, "content": content, "reply_to": payload.get("reply_to")}
        ser = MessageSerializer(data=data, context={"request": request})
        ser.is_valid(raise_exception=True)
        msg = ser.save(conversation=conv)

        # Fayllarni saqlash
        att_out = []
        for f in files:
            att = Attachment.objects.create(
                message=msg, file=f,
                original_name=getattr(f, "name", ""),
                size=getattr(f, "size", 0),
                mime_type=(getattr(f, "content_type", "") or ""),
                uploaded_by=request.user,
            )
            att_out.append(AttachmentSerializer(att, context={"request": request}).data)

        # Sender uchun read-receipt va oxirgi xabar vaqtini yangilash
        ReadReceipt.objects.get_or_create(message=msg, user=request.user)
        Conversation.objects.filter(pk=conv.pk).update(last_message_at=timezone.now())

        out = MessageSerializer(msg, context={"request": request}).data
        out["attachments"] = att_out
        return Response(out, status=201)

    # (qolgan actionlar: mark_read / summary / prescriptions / files / search — avvalgidek)



class MessageViewSet(mixins.RetrieveModelMixin,
                     mixins.UpdateModelMixin,
                     mixins.DestroyModelMixin,
                     viewsets.GenericViewSet):
    """Alohida xabar: ko‘rish / tahrirlash / soft-delete."""
    queryset = (
        Message.objects
        .select_related("conversation", "sender")
        .prefetch_related("attachments")
    )
    serializer_class = MessageSerializer
    permission_classes = [IsConversationParticipant, IsMessageOwnerOrReadOnly]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def perform_update(self, serializer):
        inst = serializer.save()
        inst.edited_at = timezone.now()
        inst.save(update_fields=["edited_at"])

    def perform_destroy(self, instance):
        instance.soft_delete()
