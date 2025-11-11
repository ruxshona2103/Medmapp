from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction

from .models import (
    Conversation,
    Participant,
    Message,
    Attachment,
    MessageReadStatus,
    Prescription,
    DoctorSummary,
)

User = get_user_model()


# ========================================
# ✅ USER TINY SERIALIZER
# ========================================
class UserTinySerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "first_name", "last_name", "full_name", "avatar_url")

    def get_full_name(self, obj):
        try:
            return obj.get_full_name()
        except:
            return obj.phone_number

    def get_avatar_url(self, obj):
        avatar_fields = ["avatar", "photo", "profile_picture"]
        request = self.context.get("request")
        for field in avatar_fields:
            if hasattr(obj, field):
                avatar = getattr(obj, field)
                if avatar:
                    return request.build_absolute_uri(avatar.url)
        return None


# ========================================
# ✅ ATTACHMENT SERIALIZER
# ========================================
class AttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    uploader = UserTinySerializer(source="uploaded_by", read_only=True)
    uploader_role = serializers.SerializerMethodField()
    preview_url = serializers.SerializerMethodField()
    formatted_size = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = (
            "id", "file", "file_url", "file_type", "mime_type", "size",
            "formatted_size", "original_name", "uploaded_at",
            "uploader", "uploader_role", "preview_url"
        )

    def get_file_url(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.file.url) if obj.file else None

    def get_uploader_role(self, obj):
        part = obj.message.conversation.participants.filter(user=obj.uploaded_by).first()
        return part.role if part else "unknown"

    def get_preview_url(self, obj):
        if obj.file_type in ["image", "video"]:
            return self.get_file_url(obj)
        return None

    def get_formatted_size(self, obj):
        size = obj.size
        for unit in ["B","KB","MB","GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

# ========================================
# ✅ PRESCRIPTION SERIALIZER
# ========================================
class PrescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prescription
        fields = "__all__"


# ========================================
# ✅ DOCTOR SUMMARY SERIALIZER
# ========================================
class DoctorSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorSummary
        fields = "__all__"


# ========================================
# ✅ MESSAGE SERIALIZER
# ========================================
class MessageSerializer(serializers.ModelSerializer):
    sender = UserTinySerializer(read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)
    reply_to_message = serializers.SerializerMethodField()
    reply_to_content = serializers.SerializerMethodField()
    is_read = serializers.SerializerMethodField()
    sender_role = serializers.SerializerMethodField()

    conversation = serializers.PrimaryKeyRelatedField(queryset=Conversation.objects.all())
    reply_to = serializers.PrimaryKeyRelatedField(
        queryset=Message.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Message
        fields = (
            "id", "conversation", "type", "content", "reply_to",
            "reply_to_message", "reply_to_content", "sender",
            "sender_role", "created_at", "edited_at", "is_deleted",
            "attachments", "is_read"
        )
        read_only_fields = (
            "id", "sender", "created_at", "edited_at",
            "is_deleted", "attachments", "sender_role",
            "reply_to_message", "reply_to_content", "is_read"
        )

    def get_reply_to_message(self, obj):
        m = obj.reply_to
        if not m:
            return None
        return {
            "id": m.id,
            "sender": m.sender.get_full_name(),
            "preview": (m.content[:60] + "...") if m.content else "",
            "created_at": m.created_at.isoformat()
        }

    def get_reply_to_content(self, obj):
        if obj.reply_to and obj.reply_to.content:
            c = obj.reply_to.content
            return c if len(c) < 100 else c[:100] + "..."
        return None

    def get_sender_role(self, obj):
        part = obj.conversation.participants.filter(user=obj.sender).first()
        return part.role if part else "unknown"

    def get_is_read(self, obj):
        request = self.context.get("request")
        if not request or request.user == obj.sender:
            return True
        return MessageReadStatus.objects.filter(message=obj, user=request.user).exists()

    def validate(self, attrs):
        conv = attrs.get("conversation")
        type = attrs.get("type")
        content = attrs.get("content")

        if type == "text" and (not content or not content.strip()):
            raise ValidationError({"content": "Matn bo‘sh bo‘lmasligi kerak"})

        if type == "file":
            files = self.context["request"].FILES.getlist("attachments")
            if not files:
                raise ValidationError({"file": "Kamida 1 ta fayl bo‘lishi kerak"})

        if attrs.get("reply_to"):
            if attrs["reply_to"].conversation != conv:
                raise ValidationError({"reply_to": "Faqat shu suhbatdagi xabarga reply bo‘ladi"})

        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        message = Message.objects.create(
            sender=request.user,
            **validated_data
        )

        # ---- ATTACHMENTS ----
        files = request.FILES.getlist("attachments") or request.FILES.getlist("files")
        for file in files:
            Attachment.objects.create(
                message=message,
                file=file,
                uploaded_by=request.user,
                original_name=file.name,
                size=file.size,
                mime_type=getattr(file, "content_type", "application/octet-stream")
            )

        # ---- READ STATUS ----
        MessageReadStatus.objects.get_or_create(
            message=message,
            user=request.user,
            defaults={"read_at": timezone.now()}
        )

        return message

# ========================================
# ✅ CONVERSATION LIST SERIALIZER
# ========================================
class ConversationSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    participants = serializers.SerializerMethodField()

    patient_info = UserTinySerializer(source="patient.user", read_only=True)
    operator_info = UserTinySerializer(source="operator", read_only=True)

    class Meta:
        model = Conversation
        fields = (
            "id", "title", "patient", "patient_info",
            "operator", "operator_info", "is_active",
            "last_message_at", "last_message",
            "last_message_preview", "unread_count",
            "participants", "created_by"
        )

    def get_last_message(self, obj):
        msg = obj.messages.order_by("-id").first()
        return MessageSerializer(msg, context=self.context).data if msg else None

    def get_last_message_preview(self, obj):
        msg = obj.messages.order_by("-id").first()
        if not msg:
            return "Suhbat boshlanmadi"
        if msg.type == "file":
            f = msg.attachments.first()
            return f"Fayl: {f.original_name}" if f else "Fayl yuborilgan"
        return msg.content[:50] + "..." if msg.content and len(msg.content) > 50 else msg.content

    def get_unread_count(self, obj):
        user = self.context["request"].user
        return obj.messages.filter(
            is_deleted=False
        ).exclude(
            read_statuses__user=user
        ).exclude(
            sender=user
        ).count()

    def get_participants(self, obj):
        parts = obj.participants.select_related("user").all()
        return [
            {
                "id": p.user.id,
                "role": p.role,
                "full_name": p.user.get_full_name(),
                "avatar": UserTinySerializer(p.user, context=self.context).data["avatar_url"],
                "last_seen": p.last_seen_at.isoformat() if p.last_seen_at else None
            }
            for p in parts
        ]


# ========================================
# ✅ CONVERSATION CREATE SERIALIZER
# ========================================
class ConversationCreateSerializer(serializers.ModelSerializer):
    patient_id = serializers.IntegerField(write_only=True)
    operator_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Conversation
        fields = ("id", "title", "patient_id", "operator_id")

    def validate(self, attrs):
        req = self.context["request"]

        patient_user = User.objects.filter(id=attrs["patient_id"]).first()
        if not patient_user:
            raise ValidationError("Bemor topilmadi")

        if not Patient.objects.filter(user=patient_user).exists():
            raise ValidationError("Bu user bemor emas")

        if attrs.get("operator_id"):
            operator = User.objects.filter(id=attrs["operator_id"], is_staff=True).first()
            if not operator:
                raise ValidationError("Operator topilmadi yoki staff emas")
        else:
            attrs["operator_id"] = req.user.id

        return attrs

    def create(self, validated_data):
        req = self.context["request"]

        patient_user = User.objects.get(id=validated_data.pop("patient_id"))
        patient_profile = patient_user.patient_profile
        operator = User.objects.get(id=validated_data.pop("operator_id"))

        conv, created = Conversation.objects.get_or_create(
            patient=patient_profile,
            operator=operator,
            defaults={
                "created_by": req.user,
                "title": validated_data.get("title") or f"{patient_user.get_full_name()} bilan suhbat",
                "last_message_at": timezone.now(),
            }
        )

        if created:
            Participant.objects.create(conversation=conv, user=patient_user, role="patient")
            Participant.objects.create(conversation=conv, user=operator, role="operator")

        return conv


# ========================================
# ✅ MESSAGE READ STATUS SERIALIZER
# ========================================
class MessageReadStatusSerializer(serializers.ModelSerializer):
    user = UserTinySerializer(read_only=True)

    class Meta:
        model = MessageReadStatus
        fields = ("id", "message", "user", "read_at", "is_read")
        read_only_fields = fields
