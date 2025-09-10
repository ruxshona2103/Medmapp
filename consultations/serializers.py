from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Conversation, Participant, Message, Attachment, DoctorSummary, Prescription

User = get_user_model()


# --------- Foydalanuvchi mini ko'rinishi
class UserTinySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "first_name", "last_name")


# --------- Attachment
class AttachmentSerializer(serializers.ModelSerializer):
    uploader = UserTinySerializer(source="uploaded_by", read_only=True)
    uploader_role = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = ("id", "file", "mime_type", "size", "original_name",
                  "uploaded_at", "uploader", "uploader_role")

    def get_uploader_role(self, obj):
        conv = obj.message.conversation
        role = conv.participants.filter(user=obj.uploaded_by).values_list("role", flat=True).first()
        return role


# --------- Message
class MessageSerializer(serializers.ModelSerializer):
    sender = UserTinySerializer(read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)
    reply_to = serializers.PrimaryKeyRelatedField(queryset=Message.objects.all(), allow_null=True, required=False)

    class Meta:
        model = Message
        fields = ("id", "type", "content", "reply_to", "sender",
                  "created_at", "edited_at", "is_deleted", "attachments")

    def validate(self, attrs):
        t = attrs.get("type", "text")
        if t == "text" and not attrs.get("content"):
            raise serializers.ValidationError({"content": "Matn bo'sh bo'lmasin."})
        return attrs

    def create(self, validated):
        request = self.context["request"]
        validated["sender"] = request.user
        return super().create(validated)


# --------- Conversation: list/detail uchun
class ConversationSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()
    participants = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ("id", "title", "patient", "doctor", "is_active",
                  "last_message_at", "last_message", "last_message_preview",
                  "unread_count", "participants")
        read_only_fields = ("patient", "doctor", "last_message_at",
                            "last_message", "last_message_preview",
                            "unread_count", "participants")

    def get_last_message(self, obj):
        last = obj.messages.order_by("-id").first()
        if not last:
            return None
        return MessageSerializer(last, context=self.context).data

    def get_last_message_preview(self, obj):
        m = obj.messages.order_by("-id").first()
        if not m:
            return ""
        if m.type == "file":
            a = m.attachments.first()
            return a.original_name if a else "Fayl"
        return (m.content or "")[:80]

    def get_unread_count(self, obj):
        u = self.context["request"].user
        return obj.messages.exclude(sender=u).exclude(read_receipts__user=u).count()

    def get_participants(self, obj):
        qs = obj.participants.select_related("user")
        return [{"id": p.user_id, "role": p.role,
                 "first_name": getattr(p.user, "first_name", None),
                 "last_name": getattr(p.user, "last_name", None)} for p in qs]


class ConversationCreateSerializer(serializers.ModelSerializer):
    doctor_id = serializers.IntegerField(write_only=True)
    patient_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Conversation
        fields = ("id", "title", "doctor_id", "patient_id")

    def create(self, validated):
        request = self.context["request"]
        doctor = User.objects.get(pk=validated.pop("doctor_id"))
        patient = User.objects.get(pk=validated.pop("patient_id"))
        conv, _ = Conversation.objects.get_or_create(
            doctor=doctor, patient=patient, defaults={"created_by": request.user, **validated}
        )
        Participant.objects.get_or_create(conversation=conv, user=doctor,  defaults={"role": "doctor"})
        Participant.objects.get_or_create(conversation=conv, user=patient, defaults={"role": "patient"})
        if request.user not in (doctor, patient):
            Participant.objects.get_or_create(conversation=conv, user=request.user, defaults={"role": "operator"})
        return conv


# --------- Shifokor xulosasi
class DoctorSummarySerializer(serializers.ModelSerializer):
    """Tavsiyalar frontendda punkt sifatida ko'rinishi uchun list ham beramiz."""
    recommendations_list = serializers.SerializerMethodField()
    author = UserTinySerializer(source="created_by", read_only=True)

    class Meta:
        model = DoctorSummary
        fields = ("id", "diagnosis", "recommendations", "recommendations_list",
                  "author", "created_at", "updated_at")

    def get_recommendations_list(self, obj):
        return [line.strip() for line in (obj.recommendations or "").splitlines() if line.strip()]


# --------- Retseptlar
class PrescriptionSerializer(serializers.ModelSerializer):
    author = UserTinySerializer(source="created_by", read_only=True)

    class Meta:
        model = Prescription
        fields = ("id", "name", "instruction", "duration_days", "notes",
                  "author", "created_at")
