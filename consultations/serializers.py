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


class UserTinySerializer(serializers.ModelSerializer):
    """
    Foydalanuvchi uchun qisqa ma'lumotlar serializeri.
    """
    full_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "first_name", "last_name", "full_name", "avatar_url")
        extra_kwargs = {
            "first_name": {"required": False},
            "last_name": {"required": False},
        }

    def get_full_name(self, obj):
        try:
            if hasattr(obj, "full_name") and obj.full_name:
                return obj.full_name
            return (
                f"{obj.first_name or ''} {obj.last_name or ''}".strip()
                or "Noma'lum foydalanuvchi"
            )
        except:
            return "Noma'lum foydalanuvchi"

    def get_avatar_url(self, obj):
        try:
            avatar_fields = ["avatar", "profile_picture", "photo"]
            for field_name in avatar_fields:
                if hasattr(obj, field_name) and getattr(obj, field_name):
                    avatar = getattr(obj, field_name)
                    request = self.context.get("request")
                    if request and avatar:
                        return request.build_absolute_uri(avatar.url)
                    break
        except:
            pass
        return None


class AttachmentSerializer(serializers.ModelSerializer):
    """
    Xabarga biriktirilgan fayllar uchun serializer.
    """
    file_url = serializers.SerializerMethodField()
    uploader = UserTinySerializer(source="uploaded_by", read_only=True)
    uploader_role = serializers.SerializerMethodField()
    preview_url = serializers.SerializerMethodField()
    formatted_size = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = (
            "id",
            "file",
            "file_url",
            "file_type",
            "mime_type",
            "size",
            "formatted_size",
            "original_name",
            "uploaded_at",
            "uploader",
            "uploader_role",
            "preview_url",
        )
        read_only_fields = (
            "size",
            "mime_type",
            "uploaded_at",
            "uploader",
            "uploader_role",
        )

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None

    def get_uploader_role(self, obj):
        try:
            participant = obj.message.conversation.participants.filter(
                user=obj.uploaded_by
            ).first()
            return participant.role if participant else "unknown"
        except:
            return "unknown"

    def get_preview_url(self, obj):
        if obj.file_type in ["image", "video"]:
            return self.get_file_url(obj)
        return None

    def get_formatted_size(self, obj):
        size = obj.size
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


class PrescriptionSerializer(serializers.ModelSerializer):
    """
    Suhbatga bog'langan retseptlar uchun serializer.
    """
    class Meta:
        model = Prescription
        fields = "__all__"


class DoctorSummarySerializer(serializers.ModelSerializer):
    """
    Suhbat uchun shifokor xulosasi uchun serializer.
    """
    class Meta:
        model = DoctorSummary
        fields = "__all__"


class MessageSerializer(serializers.ModelSerializer):
    """
    Xabarlar uchun serializer, attachments va reply_to ma'lumotlari bilan.
    """
    sender = UserTinySerializer(read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)
    reply_to_message = serializers.SerializerMethodField()
    reply_to_content = serializers.SerializerMethodField()
    is_read = serializers.SerializerMethodField()
    sender_role = serializers.SerializerMethodField()
    conversation = serializers.PrimaryKeyRelatedField(
        queryset=Conversation.objects.all()
    )
    reply_to = serializers.PrimaryKeyRelatedField(
        queryset=Message.objects.all(),
        required=False,
        allow_null=True
    )

    class Meta:
        model = Message
        fields = (
            "id",
            "conversation",
            "type",
            "content",
            "reply_to",
            "reply_to_message",
            "reply_to_content",
            "sender",
            "sender_role",
            "created_at",
            "edited_at",
            "is_deleted",
            "attachments",
            "is_read",
        )
        read_only_fields = (
            "id",
            "sender",
            "sender_role",
            "created_at",
            "edited_at",
            "is_deleted",
            "attachments",
            "reply_to_message",
            "reply_to_content",
            "is_read",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and hasattr(request, "parser_context"):
            view = request.parser_context.get("view")
            if view and hasattr(view, "conversation"):
                self.initial["conversation"] = view.conversation

    def get_reply_to_message(self, obj):
        if obj.reply_to:
            return {
                "id": obj.reply_to.id,
                "sender_id": obj.reply_to.sender.id,
                "sender_name": getattr(
                    obj.reply_to.sender,
                    "get_full_name",
                    lambda: str(obj.reply_to.sender.id),
                )(),
                "content_preview": (
                    (obj.reply_to.content[:50] + "...")
                    if len(obj.reply_to.content or "") > 50
                    else (obj.reply_to.content or "")
                ),
                "created_at": obj.reply_to.created_at.isoformat(),
            }
        return None

    def get_reply_to_content(self, obj):
        if obj.reply_to and obj.reply_to.content:
            content = obj.reply_to.content[:100]
            return content + "..." if len(obj.reply_to.content) > 100 else content
        return None

    def get_is_read(self, obj):
        request = self.context.get("request")
        if request and request.user and request.user != obj.sender:
            try:
                read_status = MessageReadStatus.objects.get(
                    message=obj, user=request.user
                )
                return read_status.is_read
            except MessageReadStatus.DoesNotExist:
                return False
        return True

    def get_sender_role(self, obj):
        try:
            participant = obj.conversation.participants.filter(user=obj.sender).first()
            return participant.role if participant else "unknown"
        except:
            return "unknown"

    def validate(self, attrs):
        """Xabar validatsiyasi"""
        conversation = attrs.get("conversation")
        message_type = attrs.get("type", "text")
        content = attrs.get("content", "")

        if not conversation:
            raise serializers.ValidationError({"conversation": "Suhbat majburiy"})

        if message_type == "text" and not content or not content.strip():
            raise serializers.ValidationError(
                {"content": "Matn xabar uchun kontent majburiy"}
            )

        if message_type == "file":
            request = self.context.get("request")
            files = []
            if request and request.FILES:
                files = request.FILES.getlist("attachments") or request.FILES.getlist("files")
            if not files:
                raise serializers.ValidationError(
                    {"files": "Fayl xabar uchun kamida bitta fayl kerak"}
                )

        reply_to_id = attrs.get("reply_to")
        if reply_to_id:
            try:
                reply_message = Message.objects.get(id=reply_to_id)
                if reply_message.conversation != conversation:
                    raise serializers.ValidationError(
                        {
                            "reply_to": "Javob faqat shu suhbatdagi xabarlarga berilishi mumkin"
                        }
                    )
                if reply_message.is_deleted:
                    raise serializers.ValidationError(
                        {"reply_to": "O'chirilgan xabarga javob berib bo'lmaydi"}
                    )
            except Message.DoesNotExist:
                raise serializers.ValidationError(
                    {"reply_to": "Javob berilmoqchi bo'lgan xabar topilmadi"}
                )

        return attrs

    def create(self, validated_data):
        """Yangi xabar yaratish"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Autentifikatsiya kerak")

        conversation = validated_data.pop("conversation")
        validated_data["sender"] = request.user
        validated_data["is_deleted"] = False  # Har doim False bilan boshlash

        with transaction.atomic():
            message = Message.objects.create(
                conversation=conversation, **validated_data
            )

            # 'attachments' yoki 'files' nomidan fayllarni olish
            files = request.FILES.getlist("attachments", [])
            if not files:
                files = request.FILES.getlist("files", [])
            attachments_data = []

            for file in files:
                try:
                    if (
                        hasattr(file, "size") and file.size > 10 * 1024 * 1024
                    ):  # 10MB limit
                        print(f"Fayl {file.name} 10MB dan katta, o'tkazib yuborildi")
                        continue

                    attachment = Attachment.objects.create(
                        message=message,
                        file=file,
                        uploaded_by=request.user,
                        original_name=getattr(file, "name", "unknown_file"),
                        size=getattr(file, "size", 0),
                        mime_type=getattr(
                            file, "content_type", "application/octet-stream"
                        ),
                    )
                    attachments_data.append(
                        AttachmentSerializer(attachment, context=self.context).data
                    )
                except Exception as e:
                    print(f"Fayl yuklashda xato ({file.name}): {e}")
                    continue

            try:
                MessageReadStatus.objects.get_or_create(
                    message=message,
                    user=request.user,
                    defaults={"read_at": timezone.now()},
                )
            except Exception as e:
                print(f"Read status yaratishda xato: {e}")

        full_data = MessageSerializer(message, context=self.context).data
        full_data["attachments"] = attachments_data
        return full_data

    def update(self, instance, validated_data):
        """Xabar tahrirlash"""
        request = self.context.get("request")
        if not request or request.user != instance.sender:
            raise serializers.ValidationError(
                "Faqat o'z xabaringizni tahrirlashingiz mumkin"
            )

        if "content" in validated_data:
            instance.content = validated_data["content"]

        instance.edited_at = timezone.now()
        instance.save(update_fields=["content", "edited_at"])

        return instance


class ConversationSerializer(serializers.ModelSerializer):
    """
    Suhbatlar uchun serializer, oxirgi xabar va ishtirokchilar bilan.
    """
    last_message = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    participants = serializers.SerializerMethodField()
    patient_info = UserTinySerializer(source="patient", read_only=True)
    operator_info = UserTinySerializer(source="operator", read_only=True)

    class Meta:
        model = Conversation
        fields = (
            "id",
            "title",
            "patient",
            "patient_info",
            "operator",
            "operator_info",
            "is_active",
            "last_message_at",
            "last_message",
            "last_message_preview",
            "unread_count",
            "participants",
            "created_by",
        )
        read_only_fields = (
            "id",
            "patient",
            "patient_info",
            "operator",
            "operator_info",
            "last_message_at",
            "last_message",
            "last_message_preview",
            "unread_count",
            "participants",
            "created_by",
        )

    def get_last_message(self, obj):
        try:
            last_msg = obj.messages.select_related("sender").order_by("-id").first()
            if last_msg:
                return MessageSerializer(last_msg, context=self.context).data
            return None
        except Exception as e:
            print(f"Last message olishda xato: {e}")
            return None

    def get_last_message_preview(self, obj):
        try:
            last_msg = obj.messages.order_by("-id").first()
            if not last_msg:
                return "Suhbat boshlanmadi"

            if last_msg.type == "file":
                attachment = last_msg.attachments.first()
                return (
                    f"Fayl: {attachment.original_name[:30]}"
                    if attachment
                    else "Fayl yuborildi"
                )

            content = last_msg.content or ""
            return content[:50] + "..." if len(content) > 50 else content
        except Exception as e:
            print(f"Last message preview olishda xato: {e}")
            return "Xabar yuklashda xatolik"

    def get_unread_count(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return 0

        user = request.user
        try:
            if user == obj.patient:
                return (
                    obj.messages.filter(sender=obj.operator, is_deleted=False)
                    .exclude(read_statuses__user=user)
                    .count()
                )
            elif user == obj.operator:
                return (
                    obj.messages.filter(sender=obj.patient, is_deleted=False)
                    .exclude(read_statuses__user=user)
                    .count()
                )
        except Exception as e:
            print(f"Unread count hisoblashda xato: {e}")
            return 0

        return 0

    def get_participants(self, obj):
        participants = []
        try:
            for participant in obj.participants.select_related("user").all():
                participant_data = {
                    "id": participant.user.id,
                    "role": participant.role,
                    "full_name": getattr(
                        participant.user,
                        "get_full_name",
                        lambda: f"{participant.user.first_name or ''} {participant.user.last_name or ''}".strip(),
                    )(),
                    "is_online": False,
                    "last_seen": (
                        participant.last_seen_at.isoformat()
                        if participant.last_seen_at
                        else None
                    ),
                }

                try:
                    user_serializer = UserTinySerializer(
                        participant.user, context=self.context
                    )
                    if user_serializer.data.get("avatar_url"):
                        participant_data["avatar_url"] = user_serializer.data[
                            "avatar_url"
                        ]
                except Exception as e:
                    print(f"User serializer xatosi: {e}")

                participants.append(participant_data)
        except Exception as e:
            print(f"Participants olishda xato: {e}")

        return participants


class ConversationCreateSerializer(serializers.ModelSerializer):
    """
    Yangi suhbat yaratish uchun serializer.
    """
    patient_id = serializers.IntegerField(write_only=True)
    operator_id = serializers.IntegerField(
        write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = Conversation
        fields = ("id", "title", "patient_id", "operator_id")
        read_only_fields = ("id",)

    def validate_patient_id(self, value):
        """Bemor ID validatsiyasi"""
        try:
            User.objects.get(pk=value)
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("Bemor topilmadi")

    def validate_operator_id(self, value):
        """Operator ID validatsiyasi"""
        if value is not None:
            try:
                operator = User.objects.get(pk=value)
                if not operator.is_staff:
                    raise serializers.ValidationError(
                        "Faqat staff foydalanuvchilar operator bo'lishi mumkin"
                    )
                return value
            except User.DoesNotExist:
                raise serializers.ValidationError("Operator topilmadi")
        return None

    def validate(self, attrs):
        """Umumiy validatsiya"""
        patient_id = attrs.get("patient_id")
        operator_id = attrs.get("operator_id")
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Autentifikatsiya kerak")

        if not request.user.is_staff:
            raise serializers.ValidationError(
                "Faqat admin/staff foydalanuvchilar suhbat yaratishi mumkin"
            )

        if operator_id is None:
            if not request.user.is_staff:
                raise serializers.ValidationError(
                    "Operator ID majburiy (staff user kerak)"
                )
            attrs["operator_id"] = request.user.id

        return attrs

    def create(self, validated_data):
        """Yangi suhbat yaratish"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Autentifikatsiya kerak")

        patient_id = validated_data.pop("patient_id")
        operator_id = validated_data.pop("operator_id")

        try:
            patient = User.objects.get(pk=patient_id)
            operator = User.objects.get(pk=operator_id)
        except User.DoesNotExist as e:
            raise serializers.ValidationError(f"Foydalanuvchi topilmadi: {str(e)}")

        conversation, created = Conversation.objects.get_or_create(
            patient=patient,
            operator=operator,
            defaults={
                "created_by": request.user,
                "title": validated_data.get(
                    "title",
                    f"Suhbat: {getattr(patient, 'get_full_name', lambda: patient.username)() or patient.username}",
                ),
                "last_message_at": timezone.now(),
            },
        )

        if created:
            try:
                Participant.objects.get_or_create(
                    conversation=conversation,
                    user=patient,
                    defaults={"role": "patient", "joined_at": timezone.now()},
                )
                Participant.objects.get_or_create(
                    conversation=conversation,
                    user=operator,
                    defaults={"role": "operator", "joined_at": timezone.now()},
                )

                welcome_content = f"Salom! Suhbat boshlandi. {getattr(request.user, 'get_full_name', lambda: request.user.username)() or request.user.username} tomonidan yaratildi."
                welcome_message = Message.objects.create(
                    conversation=conversation,
                    sender=request.user,
                    type="system",
                    content=welcome_content,
                )

                MessageReadStatus.objects.get_or_create(
                    message=welcome_message,
                    user=request.user,
                    defaults={"read_at": timezone.now()},
                )
            except Exception as e:
                print(f"Suhbat yaratishda qo'shimcha xatolar: {e}")

        return conversation


class MessageReadStatusSerializer(serializers.ModelSerializer):
    """
    Xabar o'qilgan holatini kuzatish uchun serializer.
    """
    user = UserTinySerializer(read_only=True)
    message_id = serializers.IntegerField(source="message.id", read_only=True)

    class Meta:
        model = MessageReadStatus
        fields = ("id", "message_id", "user", "read_at", "is_read")
        read_only_fields = ("id", "message_id", "user", "read_at", "is_read")

    def create(self, validated_data):
        """O'qilgan status yaratish"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Autentifikatsiya kerak")

        message_id = validated_data.get("message_id")
        try:
            message = Message.objects.get(id=message_id)
        except Message.DoesNotExist:
            raise serializers.ValidationError("Xabar topilmadi")

        participants = message.conversation.participants.all()
        if request.user not in [p.user for p in participants]:
            raise serializers.ValidationError("Suhbat ishtirokchisi emassiz")

        if request.user == message.sender:
            raise serializers.ValidationError(
                "O'z xabaringizni o'qilgan deb belgilash mumkin emas"
            )

        status, created = MessageReadStatus.objects.get_or_create(
            message=message,
            user=request.user,
            defaults={"read_at": timezone.now(), "is_read": True},
        )

        if created:
            try:
                message.mark_as_read(request.user)
                message.conversation.last_message_at = timezone.now()
                message.conversation.save(update_fields=["last_message_at"])
                participant = participants.filter(user=request.user).first()
                if participant:
                    participant.last_seen_at = timezone.now()
                    participant.save(update_fields=["last_seen_at"])
            except Exception as e:
                print(f"Read status yangilashda xato: {e}")

        return status
