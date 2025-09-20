from django.db.models import Q
from django.http import QueryDict
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from rest_framework.request import Request

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import (
    Conversation,
    Message,
    Attachment,
    ReadReceipt,
    DoctorSummary,
    Prescription,
    Participant,
)
from .serializers import (
    ConversationSerializer,
    ConversationCreateSerializer,
    MessageSerializer,
    AttachmentSerializer,
    DoctorSummarySerializer,
    PrescriptionSerializer,
)

User = get_user_model()


class ConversationViewSet(viewsets.ModelViewSet):
    queryset = Conversation.objects.all().select_related("patient", "doctor")
    serializer_class = ConversationSerializer
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_permissions(self):
        """Permission'larni dinamik ravishda belgilash"""
        if self.action in ["operator_messages"]:
            # Operator uchun permission'lar
            from rest_framework.permissions import AllowAny

            return [AllowAny()]  # Operator uchun vaqtincha allow
        return super().get_permissions()

    def get_queryset(self):
        u = self.request.user
        # Operatorlar uchun doctor=None suhbatlarni ham ko'rsatish
        return (
            Conversation.objects.filter(
                Q(participants__user=u)
                | Q(participants__user=u, participants__role="operator")
            )
            .filter(is_active=True)
            .distinct()
            .select_related("patient", "doctor")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return ConversationCreateSerializer
        return ConversationSerializer

    def create(self, request: Request, *args, **kwargs):
        """Operator va doctor uchun suhbat yaratish"""
        try:
            patient_id = request.data.get("patient_id")
            doctor_id = request.data.get("doctor_id")

            if not patient_id:
                return Response(
                    {"detail": "patient_id majburiy"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                patient_id = int(patient_id)
            except (ValueError, TypeError):
                return Response(
                    {"detail": "ID noto'g'ri formatda"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Operator ekanligini tekshirish
            is_operator = request.user.is_staff or (
                hasattr(request.user, "role") and request.user.role == "operator"
            )

            try:
                patient = User.objects.get(pk=patient_id)
            except User.DoesNotExist:
                return Response(
                    {"detail": "Bemor topilmadi"}, status=status.HTTP_404_NOT_FOUND
                )

            # Doctor ID berilgan bo'lsa
            if doctor_id:
                try:
                    doctor_id = int(doctor_id)
                    doctor = User.objects.get(pk=doctor_id)

                    # Doctor uchun suhbat
                    conversation, created = Conversation.objects.get_or_create(
                        patient=patient,
                        doctor=doctor,
                        defaults={
                            "created_by": request.user,
                            "title": f"Suhbat: {patient.first_name} {patient.last_name}",
                        },
                    )

                    if created:
                        # Participant'larni qo'shish
                        Participant.objects.get_or_create(
                            conversation=conversation,
                            user=patient,
                            defaults={"role": "patient"},
                        )
                        Participant.objects.get_or_create(
                            conversation=conversation,
                            user=doctor,
                            defaults={"role": "doctor"},
                        )
                        if request.user != doctor and is_operator:
                            Participant.objects.get_or_create(
                                conversation=conversation,
                                user=request.user,
                                defaults={"role": "operator"},
                            )

                except User.DoesNotExist:
                    return Response(
                        {"detail": "Shifokor topilmadi"},
                        status=status.HTTP_404_NOT_FOUND,
                    )
            else:
                # Operator uchun doctor=None bo'lgan suhbat
                if not is_operator:
                    return Response(
                        {
                            "detail": "Faqat operatorlar doctor'siz suhbat yaratishi mumkin"
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )

                conversation, created = Conversation.objects.get_or_create(
                    patient=patient,
                    doctor=None,  # Operator uchun
                    defaults={
                        "created_by": request.user,
                        "title": f"Operator suhbat: {patient.first_name} {patient.last_name}",
                    },
                )

                if created:
                    # Participant'larni qo'shish
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

            serializer = ConversationSerializer(conversation)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"detail": f"Xatolik yuz berdi: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    # ---- Swagger uchun messages POST body (to'g'irlangan)
    message_body = openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "type": openapi.Schema(
                type=openapi.TYPE_STRING, enum=["text", "file"], default="text"
            ),
            "content": openapi.Schema(
                type=openapi.TYPE_STRING, description="Matn xabar"
            ),
            "reply_to": openapi.Schema(type=openapi.TYPE_INTEGER, nullable=True),
        },
        required=[],
    )

    # TO'G'IRLANGAN: in_ parametri qo'shildi
    @swagger_auto_schema(
        method="get",
        responses={200: MessageSerializer(many=True)},
        manual_parameters=[
            openapi.Parameter(
                name="since_id",
                in_=openapi.IN_QUERY,  # ← Bu qo'shildi
                type=openapi.TYPE_INTEGER,
                description="Oxirgi yuklangan xabar ID'sidan keyingi xabarlar",
                required=False,
            ),
            openapi.Parameter(
                name="q",
                in_=openapi.IN_QUERY,  # ← Bu qo'shildi
                type=openapi.TYPE_STRING,
                description="Qidiruv so'zi",
                required=False,
            ),
        ],
    )
    @swagger_auto_schema(
        method="post", request_body=message_body, responses={201: MessageSerializer}
    )
    @action(
        detail=True,
        methods=["get", "post"],
        url_path="messages",
        parser_classes=[JSONParser, FormParser, MultiPartParser],
    )
    def messages(self, request: Request, pk=None):
        """Suhbat xabarlari - GET: ro'yxat, POST: yuborish"""
        try:
            # Suhbat obyektini olamiz
            conv = self.get_object()
            context = {"request": request}  # Barcha serializerlar uchun context

            # ---------- GET: xabarlar ro'yxati ----------
            if request.method.lower() == "get":
                qs = (
                    conv.messages.select_related("sender")
                    .prefetch_related("attachments", "reply_to")
                    .order_by("id")
                )

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
                    # Sahifalangan (paginated) javob
                    messages_data = MessageSerializer(
                        page, many=True, context=context
                    ).data
                    # get_paginated_response faqat xabarlar ro'yxatini qaytaradi, shuning uchun
                    # uni o'zgartirib, conversation'ni ham qo'shamiz.
                    paginated_response = self.get_paginated_response(messages_data)
                    paginated_response.data["conversation"] = ConversationSerializer(
                        conv, context=context
                    ).data
                    return paginated_response

                # QO'SHILDI: Sahifalanmagan (non-paginated) holat uchun javob
                messages_data = MessageSerializer(qs, many=True, context=context).data
                return Response(
                    {
                        "conversation": ConversationSerializer(
                            conv, context=context
                        ).data,
                        "results": messages_data,
                    }
                )

            # ---------- POST: xabar yuborish ----------
            elif request.method.lower() == "post":
                # ... POST logikasi (avvalgidek qoladi, xatolik yo'q edi)
                payload = (
                    dict(request.data)
                    if not isinstance(request.data, QueryDict)
                    else dict(request.data)
                )
                files = (
                    request.FILES.getlist("attachments")
                    if hasattr(request, "FILES")
                    else []
                )
                msg_type = payload.get("type", ["file" if files else "text"])[0]
                content = payload.get("content", [""])[0]

                if msg_type == "text" and not content.strip():
                    return Response({"detail": "Matn bo'sh bo'lmasin."}, status=400)
                if msg_type == "file" and not files:
                    return Response(
                        {"detail": "Kamida bitta fayl biriktiring."}, status=400
                    )

                data = {
                    "type": msg_type,
                    "content": content,
                    "reply_to": payload.get("reply_to", [None])[0],
                }

                ser = MessageSerializer(data=data, context=context)
                if ser.is_valid():
                    msg = ser.save(conversation=conv, sender=request.user)

                    # Fayllarni saqlash
                    for f in files:
                        Attachment.objects.create(
                            message=msg,
                            file=f,
                            original_name=getattr(f, "name", ""),
                            size=getattr(f, "size", 0),
                            mime_type=getattr(f, "content_type", ""),
                            uploaded_by=request.user,
                        )

                    Conversation.objects.filter(pk=conv.pk).update(
                        last_message_at=timezone.now()
                    )
                    ReadReceipt.objects.get_or_create(message=msg, user=request.user)

                    out_data = MessageSerializer(msg, context=context).data
                    return Response(out_data, status=201)

                return Response(ser.errors, status=400)

        except Exception as e:
            return Response(
                {"detail": f"Xabar bilan ishlashda xato: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request: Request, pk=None):
        """Barcha xabarlarni o'qilgan deb belgilash"""
        try:
            conv = self.get_object()
            messages = conv.messages.exclude(is_deleted=True)

            updated_count = 0
            for msg in messages:
                if ReadReceipt.objects.get_or_create(message=msg, user=request.user)[1]:
                    updated_count += 1

            # Oxirgi xabarni o'qilgan deb belgilash
            last_msg = messages.order_by("-id").first()
            if last_msg:
                if ReadReceipt.objects.get_or_create(
                    message=last_msg, user=request.user
                )[1]:
                    updated_count += 1

            return Response(
                {"detail": f"{updated_count} ta xabar o'qilgan deb belgilandi"},
                status=200,
            )

        except Exception as e:
            return Response(
                {"detail": f"O'qilgan deb belgilashda xato: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["get"], url_path="summary")
    def summary(self, request: Request, pk=None):
        """Shifokor xulosasi"""
        try:
            conv = self.get_object()
            try:
                summary = conv.summary
                serializer = DoctorSummarySerializer(summary)
                return Response(serializer.data)
            except DoctorSummary.DoesNotExist:
                return Response({"detail": "Xulosa hali yaratilmagan"}, status=404)
        except Exception as e:
            return Response(
                {"detail": f"Xulosa olishda xato: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"], url_path="summary")
    def create_summary(self, request: Request, pk=None):
        """Shifokor xulosasini yaratish"""
        try:
            conv = self.get_object()
            # Faqat doctor yoki operator yaratishi mumkin
            is_operator = request.user.is_staff or (
                hasattr(request.user, "role") and request.user.role == "operator"
            )
            if not (request.user == conv.doctor or is_operator):
                return Response(
                    {"detail": "Faqat shifokor yoki operator xulosa yaratishi mumkin"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            data = request.data.copy()
            data["conversation"] = conv.id
            data["created_by"] = request.user.id

            serializer = DoctorSummarySerializer(data=data)
            if serializer.is_valid():
                summary = serializer.save()
                return Response(DoctorSummarySerializer(summary).data, status=201)
            return Response(serializer.errors, status=400)
        except Exception as e:
            return Response(
                {"detail": f"Xulosa yaratishda xato: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["get"], url_path="prescriptions")
    def prescriptions(self, request: Request, pk=None):
        """Retseptlar ro'yxati"""
        try:
            conv = self.get_object()
            qs = conv.prescriptions.select_related("created_by").order_by("-id")
            serializer = PrescriptionSerializer(qs, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {"detail": f"Retseptlarni olishda xato: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"], url_path="prescriptions")
    def create_prescription(self, request: Request, pk=None):
        """Yangi retsept yaratish"""
        try:
            conv = self.get_object()
            # Faqat doctor yoki operator yaratishi mumkin
            is_operator = request.user.is_staff or (
                hasattr(request.user, "role") and request.user.role == "operator"
            )
            if not (request.user == conv.doctor or is_operator):
                return Response(
                    {"detail": "Faqat shifokor yoki operator retsept yaratishi mumkin"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            data = request.data.copy()
            data["conversation"] = conv.id
            data["created_by"] = request.user.id

            serializer = PrescriptionSerializer(data=data)
            if serializer.is_valid():
                prescription = serializer.save()
                return Response(PrescriptionSerializer(prescription).data, status=201)
            return Response(serializer.errors, status=400)
        except Exception as e:
            return Response(
                {"detail": f"Retsept yaratishda xato: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["get"], url_path="files")
    def files(self, request: Request, pk=None):
        """Suhbatdagi barcha fayllar"""
        try:
            conv = self.get_object()
            qs = (
                Attachment.objects.filter(message__conversation=conv)
                .select_related("uploaded_by")
                .order_by("-uploaded_at")
            )

            page = self.paginate_queryset(qs)
            if page is not None:
                serializer = AttachmentSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = AttachmentSerializer(qs, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {"detail": f"Fayllarni olishda xato: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"], url_path="search")
    def search_conversations(self, request: Request):
        """Suhbatlarni qidirish"""
        try:
            q = request.query_params.get("q", "")
            if not q.strip():
                return Response({"detail": "Qidiruv so'zi majburiy"}, status=400)

            u = request.user
            conversations = (
                Conversation.objects.filter(
                    Q(title__icontains=q)
                    | Q(patient__first_name__icontains=q)
                    | Q(patient__last_name__icontains=q)
                    | Q(doctor__first_name__icontains=q)
                    | Q(doctor__last_name__icontains=q)
                )
                .filter(participants__user=u, is_active=True)
                .distinct()
                .select_related("patient", "doctor")
                .order_by("-last_message_at")[:20]
            )

            serializer = ConversationSerializer(conversations, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {"detail": f"Qidirishda xato: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    # TO'G'IRLANGAN: Swagger parametrlari
    @swagger_auto_schema(
        method="get",
        responses={
            200: openapi.Response("Xabarlar ro'yxati", MessageSerializer(many=True))
        },
        manual_parameters=[
            openapi.Parameter(
                name="since_id",
                in_=openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                description="Oxirgi yuklangan xabar ID'sidan keyingi xabarlar",
                required=False,
            ),
            openapi.Parameter(
                name="q",
                in_=openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Qidiruv so'zi",
                required=False,
            ),
        ],
    )
    @swagger_auto_schema(
        method="post",
        request_body=message_body,
        responses={201: openapi.Response("Yangi xabar", MessageSerializer)},
    )
    @action(
        detail=False,
        methods=["get", "post"],
        url_path="operator/(?P<patient_id>\d+)/messages",
        parser_classes=[JSONParser, FormParser, MultiPartParser],
    )
    def operator_messages(self, request: Request, patient_id=None):
        """Operator uchun bemor ID bo'yicha suhbat va xabarlar"""
        try:
            # patient_id ni int ga aylantirish
            try:
                patient_id = int(patient_id)
            except (ValueError, TypeError):
                return Response(
                    {"detail": "Noto'g'ri bemor ID"}, status=status.HTTP_400_BAD_REQUEST
                )

            # Operator ekanligini tekshirish
            is_operator = request.user.is_staff or (
                hasattr(request.user, "role") and request.user.role == "operator"
            )
            if not is_operator:
                return Response(
                    {"detail": "Faqat operatorlar foydalanishi mumkin"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Bemor mavjudligini tekshirish
            try:
                patient = User.objects.get(pk=patient_id)
            except User.DoesNotExist:
                return Response(
                    {"detail": "Bemor topilmadi"}, status=status.HTTP_404_NOT_FOUND
                )

            # Operator uchun doctor=None bo'lgan suhbat
            conversation, created = Conversation.objects.get_or_create(
                patient=patient,
                doctor=None,  # Operator uchun
                defaults={
                    "created_by": request.user,
                    "title": f"Operator suhbat: {patient.first_name} {patient.last_name}",
                },
            )

            if created:
                # Participant'larni qo'shish
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

            # GET: xabarlar ro'yxati
            if request.method == "GET":
                qs = (
                    conversation.messages.select_related("sender")
                    .prefetch_related("attachments__uploaded_by")
                    .order_by("id")
                )

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
                    messages_data = MessageSerializer(
                        page, many=True, context={"request": request}
                    ).data
                    return self.get_paginated_response(
                        {
                            "conversation": ConversationSerializer(conversation).data,
                            "results": messages_data,
                        }
                    )

                messages_data = MessageSerializer(
                    qs, many=True, context={"request": request}
                ).data
                return Response(
                    {
                        "conversation": ConversationSerializer(conversation).data,
                        "results": messages_data,
                    }
                )

            # POST: xabar yuborish
            elif request.method == "POST":
                payload = (
                    dict(request.data)
                    if isinstance(request.data, QueryDict)
                    else dict(request.data)
                )
                files = (
                    request.FILES.getlist("attachments")
                    if hasattr(request, "FILES")
                    else []
                )

                msg_type = payload.get("type") or ("file" if files else "text")
                content = payload.get("content", "")

                if msg_type == "text" and not content.strip():
                    return Response({"content": "Matn bo'sh bo'lmasin."}, status=400)
                if msg_type == "file" and not files:
                    return Response(
                        {"attachments": "Kamida bitta fayl biriktiring."}, status=400
                    )

                data = {
                    "type": msg_type,
                    "content": content,
                    "reply_to": payload.get("reply_to"),
                }

                context = {"request": request}
                ser = MessageSerializer(data=data, context=context)

                if ser.is_valid():
                    msg = ser.save(conversation=conversation, sender=request.user)

                    # Fayllarni saqlash
                    att_out = []
                    for f in files:
                        if hasattr(f, "name") and f.name:
                            att = Attachment.objects.create(
                                message=msg,
                                file=f,
                                original_name=getattr(f, "name", ""),
                                size=getattr(f, "size", 0),
                                mime_type=getattr(f, "content_type", ""),
                                uploaded_by=request.user,
                            )
                            att_out.append(
                                AttachmentSerializer(att, context=context).data
                            )

                    # Read receipt va last_message_at yangilash
                    ReadReceipt.objects.get_or_create(message=msg, user=request.user)
                    Conversation.objects.filter(pk=conversation.pk).update(
                        last_message_at=timezone.now()
                    )

                    out = MessageSerializer(msg, context=context).data
                    out["attachments"] = att_out
                    return Response(out, status=201)
                else:
                    return Response(ser.errors, status=400)

        except Exception as e:
            return Response(
                {"detail": f"Operator xabar bilan ishlashda xato: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"], url_path="operator/mark-read")
    def operator_mark_read(self, request: Request, pk=None):
        """Operator uchun barcha xabarlarni o'qilgan deb belgilash"""
        try:
            # Operator ekanligini tekshirish
            is_operator = request.user.is_staff or (
                hasattr(request.user, "role") and request.user.role == "operator"
            )
            if not is_operator:
                return Response(
                    {"detail": "Faqat operatorlar foydalanishi mumkin"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            conv = self.get_object()
            messages = conv.messages.exclude(is_deleted=True)

            updated_count = 0
            for msg in messages:
                if ReadReceipt.objects.get_or_create(message=msg, user=request.user)[1]:
                    updated_count += 1

            last_msg = messages.order_by("-id").first()
            if last_msg:
                if ReadReceipt.objects.get_or_create(
                    message=last_msg, user=request.user
                )[1]:
                    updated_count += 1

            return Response(
                {"detail": f"{updated_count} ta xabar o'qilgan deb belgilandi"},
                status=200,
            )

        except Exception as e:
            return Response(
                {"detail": f"Operator o'qilgan deb belgilashda xato: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class MessageViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Alohida xabar: ko'rish / tahrirlash / soft-delete."""

    def get_queryset(self):
        return (
            Message.objects.select_related("conversation", "sender")
            .prefetch_related("attachments")
            .filter(conversation__participants__user=self.request.user)
        )

    serializer_class = MessageSerializer
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def perform_update(self, serializer):
        inst = serializer.save()
        inst.edited_at = timezone.now()
        inst.save(update_fields=["edited_at"])

    def perform_destroy(self, instance):
        instance.soft_delete()

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read_single(self, request: Request, pk=None):
        """Bitta xabarni o'qilgan deb belgilash"""
        try:
            message = self.get_object()
            ReadReceipt.objects.get_or_create(message=message, user=request.user)
            return Response({"detail": "Xabar o'qilgan deb belgilandi"}, status=200)
        except Exception as e:
            return Response(
                {"detail": f"O'qilgan deb belgilashda xato: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"], url_path="reply")
    def create_reply(self, request: Request, pk=None):
        """Xabarga javob yuborish"""
        try:
            message = self.get_object()
            conv = message.conversation

            # Reply ni yaratish
            data = {
                "type": "text",
                "content": request.data.get("content", ""),
                "reply_to": message.id,
                "conversation": conv.id,
            }

            context = {"request": request}
            serializer = MessageSerializer(data=data, context=context)
            if serializer.is_valid():
                reply_msg = serializer.save(sender=request.user)
                ReadReceipt.objects.get_or_create(message=reply_msg, user=request.user)
                Conversation.objects.filter(pk=conv.pk).update(
                    last_message_at=timezone.now()
                )
                return Response(
                    MessageSerializer(reply_msg, context=context).data, status=201
                )

            return Response(serializer.errors, status=400)
        except Exception as e:
            return Response(
                {"detail": f"Javob yuborishda xato: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class DoctorSummaryViewSet(viewsets.ModelViewSet):
    """Shifokor xulosalari"""

    queryset = DoctorSummary.objects.select_related("conversation", "created_by")
    serializer_class = DoctorSummarySerializer

    def get_queryset(self):
        return self.queryset.filter(conversation__participants__user=self.request.user)

    def perform_create(self, serializer):
        # Faqat shifokor yoki operator yaratishi mumkin
        is_operator = self.request.user.is_staff or (
            hasattr(self.request.user, "role") and self.request.user.role == "operator"
        )
        if not (
            self.request.user.is_staff
            or is_operator
            or getattr(self.request.user, "is_doctor", False)
        ):
            raise PermissionDenied(
                "Faqat shifokor yoki operator xulosa yaratishi mumkin"
            )
        serializer.save(created_by=self.request.user)


class PrescriptionViewSet(viewsets.ModelViewSet):
    """Retseptlar"""

    queryset = Prescription.objects.select_related("conversation", "created_by")
    serializer_class = PrescriptionSerializer

    def get_queryset(self):
        return self.queryset.filter(conversation__participants__user=self.request.user)

    def perform_create(self, serializer):
        # Faqat shifokor yoki operator yaratishi mumkin
        is_operator = self.request.user.is_staff or (
            hasattr(self.request.user, "role") and self.request.user.role == "operator"
        )
        if not (
            self.request.user.is_staff
            or is_operator
            or getattr(self.request.user, "is_doctor", False)
        ):
            raise PermissionDenied(
                "Faqat shifokor yoki operator retsept yaratishi mumkin"
            )
        serializer.save(created_by=self.request.user)
