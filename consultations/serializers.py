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
from patients.models import Patient

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
        except Exception:
            return getattr(obj, 'phone_number', str(obj))

    def get_avatar_url(self, obj):
        avatar_fields = ["avatar", "photo", "profile_picture"]
        request = self.context.get("request")
        if not request:
            return None
        for field in avatar_fields:
            if hasattr(obj, field):
                avatar = getattr(obj, field)
                if avatar:
                    try:
                        return request.build_absolute_uri(avatar.url)
                    except Exception:
                        pass
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
            "id", "file_url", "file_type", "mime_type", "size",
            "formatted_size", "original_name", "uploaded_at",
            "uploader", "uploader_role", "preview_url"
        )

    def get_file_url(self, obj):
        request = self.context.get("request")
        if not request or not obj.file:
            return None
        try:
            return request.build_absolute_uri(obj.file.url)
        except Exception:
            return None

    def get_uploader_role(self, obj):
        try:
            part = obj.message.conversation.participants.filter(user=obj.uploaded_by).first()
            return part.role if part else "unknown"
        except Exception:
            return "unknown"

    def get_preview_url(self, obj):
        if obj.file_type in ["image", "video"]:
            return self.get_file_url(obj)
        return None

    def get_formatted_size(self, obj):
        size = obj.size
        for unit in ["B", "KB", "MB", "GB"]:
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
    operator_name = serializers.SerializerMethodField()

    class Meta:
        model = DoctorSummary
        fields = "__all__"

    def get_operator_name(self, obj):
        if obj.operator:
            return obj.operator.get_full_name()
        return None

# =====================================
# ✅ MESSAGE SERIALIZER (TO'G'RILANGAN)
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
        # Modelda 'participants' related_name mavjudligiga ishonch hosil qiling
        try:
            part = obj.conversation.participants.filter(user=obj.sender).first()
            return part.role if part else "unknown"
        except AttributeError:
            # Agar 'participants' topilmasa
            return "unknown"

    def get_is_read(self, obj):
        request = self.context.get("request")
        if not request or not hasattr(request, "user") or request.user == obj.sender:
            return True

        # Modelda 'read_statuses' related_name mavjudligiga ishonch hosil qiling
        try:
            # MessageReadStatus o'rniga modeldagi related_name'ni ishlatgan ma'qul
            return obj.read_statuses.filter(user=request.user).exists()
        except Exception:
            # Agar MessageReadStatus topilmasa yoki xato bo'lsa
            return False

    def validate(self, attrs):
        conv = attrs.get("conversation")
        type = attrs.get("type")
        content = attrs.get("content")
        request = self.context.get("request")

        if not request:
            raise ValidationError("Serializer context'da 'request' topilmadi.")

        if type == "text" and (not content or not content.strip()):
            raise ValidationError({"content": "Matn bo'sh bo'lmasligi kerak"})

        # --- ❗️ FAYL VALIDATION'NI VIEWS.PY GA QO'LDIK ---
        # type == "file" bo'lsa, validation views.py'da amalga oshiriladi
        # chunki fayllar views.py'da to'g'ridan-to'g'ri Attachment modeliga yoziladi
        # Bu yerda validation qilmaslik kerak
        # --- TUZATISH TUGADI ---

        if attrs.get("reply_to"):
            if attrs["reply_to"].conversation != conv:
                raise ValidationError({"reply_to": "Faqat shu suhbatdagi xabarga reply bo‘ladi"})

        return attrs

    def create(self, validated_data):
        request = self.context["request"]

        # Message obyektini yaratamiz
        message = Message.objects.create(
            sender=request.user,
            **validated_data
        )

        # ---- ATTACHMENTS ----
        # MUHIM: Fayllar views.py'da to'g'ridan-to'g'ri Attachment modeliga yoziladi
        # Bu yerda attachment yaratish KERAK EMAS, chunki views.py buni qiladi.
        # Agar bu yerda ham yaratilsa, fayllar ikki marta saqlanadi (duplicate)!
        # Faqat oddiy /messages/ endpoint orqali fayl yuborilganda ishlaydi (attachments nomi bilan)
        files = request.FILES.getlist("attachments")  # Faqat "attachments" nomini tekshiramiz

        if files:
            # Agar serializer to'g'ridan-to'g'ri ishlatilsa (POST /messages/)
            for file in files:
                Attachment.objects.create(
                    message=message,
                    file=file,
                    uploaded_by=request.user
                )

        # ---- READ STATUS ----
        # Xabarni yuborgan odam avtomatik o'qigan hisoblanadi
        MessageReadStatus.objects.get_or_create(
            message=message,
            user=request.user,
            defaults={"read_at": timezone.now()}
        )

        # Suhbatning 'last_message_at' vaqtini yangilaymiz
        if validated_data.get("conversation"):
            validated_data["conversation"].last_message_at = timezone.now()
            validated_data["conversation"].save(update_fields=['last_message_at'])

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
        try:
            msg = obj.messages.order_by("-id").first()
            return MessageSerializer(msg, context=self.context).data if msg else None
        except Exception:
            return None

    def get_last_message_preview(self, obj):
        try:
            msg = obj.messages.order_by("-id").first()
            if not msg:
                return "Suhbat boshlanmadi"
            if msg.type == "file":
                f = msg.attachments.first()
                return f"Fayl: {f.original_name}" if f else "Fayl yuborilgan"
            return msg.content[:50] + "..." if msg.content and len(msg.content) > 50 else (msg.content or "")
        except Exception:
            return "Suhbat boshlanmadi"

    def get_unread_count(self, obj):
        try:
            user = self.context["request"].user
            return obj.messages.filter(
                is_deleted=False
            ).exclude(
                read_statuses__user=user
            ).exclude(
                sender=user
            ).count()
        except Exception:
            return 0

    def get_participants(self, obj):
        try:
            parts = obj.participants.select_related("user").all()
            return [
                {
                    "id": p.user.id,
                    "role": p.role,
                    "full_name": p.user.get_full_name(),
                    "avatar": UserTinySerializer(p.user, context=self.context).data.get("avatar_url"),
                    "last_seen": p.last_seen_at.isoformat() if p.last_seen_at else None
                }
                for p in parts
            ]
        except Exception:
            return []

class ConversationCreateSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, allow_blank=True)
    patient_profile_id = serializers.IntegerField(write_only=True)
    operator_id = serializers.IntegerField(write_only=True, required=False)

    def validate(self, attrs):
        req = self.context["request"]

        # ✅ PATIENT PROFILNI TEKSHIRAMIZ
        try:
            patient_profile = Patient.objects.get(id=attrs["patient_profile_id"])
        except Patient.DoesNotExist:
            raise serializers.ValidationError({
                "patient_profile_id": "Bunday patient mavjud emas"
            })

        if not patient_profile.user:
            raise serializers.ValidationError({
                "patient_profile_id": "Bu patientga bog‘langan user topilmadi"
            })

        # ✅ OPERATOR (default → request.user)
        operator_id = attrs.get("operator_id") or req.user.id
        try:
            operator = User.objects.get(id=operator_id)
        except User.DoesNotExist:
            raise serializers.ValidationError({"operator_id": "Operator topilmadi"})

        attrs["patient_profile"] = patient_profile
        attrs["operator"] = operator
        return attrs

    def create(self, validated_data):
        req = self.context["request"]

        patient_profile = validated_data["patient_profile"]
        operator = validated_data["operator"]
        title = validated_data.get("title") or f"{patient_profile.full_name} bilan suhbat"

        # ✅ Mavjud suhbat bor-yo‘q tekshiramiz
        conv, created = Conversation.objects.get_or_create(
            patient=patient_profile,
            operator=operator,
            is_active=True,
            defaults={
                "title": title,
                "created_by": req.user,
            }
        )

        # ✅ ✅ ✅ FIX — PARTICIPANT yaratish (muammo shu joyda edi!)
        from consultations.models import Participant

        Participant.objects.get_or_create(
            conversation=conv,
            user=patient_profile.user,
            defaults={"role": "patient"}
        )

        Participant.objects.get_or_create(
            conversation=conv,
            user=operator,
            defaults={"role": "operator"}
        )
        # ✅ ✅ ✅ FIX tugadi

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
