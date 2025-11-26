# partners/serializers.py
# ===============================================================
# HAMKOR PANEL - SERIALIZERS (MAXFIY MA'LUMOTLARSIZ!)
# ===============================================================

from rest_framework import serializers
from .models import Partner, PartnerResponseDocument
from patients.models import Patient, PatientDocument
from applications.models import Application
from core.models import Stage, Tag


# ===============================================================
# PATIENT SERIALIZERS - Maxfiy ma'lumotlarsiz
# ===============================================================

class PartnerPatientDocumentSerializer(serializers.ModelSerializer):
    """
    Bemor hujjatlari - faqat file ma'lumotlari

    ❌ Maxfiy ma'lumotlar yo'q
    """
    file_url = serializers.SerializerMethodField()
    file_size_mb = serializers.SerializerMethodField()

    class Meta:
        model = PatientDocument
        fields = [
            'id',
            'file_name',
            'file_url',
            'file_size_mb',
            'uploaded_at',
        ]

    def get_file_url(self, obj):
        """File URL"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

    def get_file_size_mb(self, obj):
        """File size (MB)"""
        if obj.file:
            return round(obj.file.size / (1024 * 1024), 2)
        return 0


class PartnerApplicationSerializer(serializers.ModelSerializer):
    """
    Arizalar - faqat asosiy ma'lumotlar

    ❌ Maxfiy ma'lumotlar yo'q
    """
    stage_name = serializers.CharField(source='stage.title', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Application
        fields = [
            'id',
            'application_id',
            'clinic_name',
            'desired_surgery_date',
            'status',
            'status_display',
            'stage_name',
            'created_at',
        ]


class PartnerResponseDocumentSerializer(serializers.ModelSerializer):
    """
    Hamkor javob xatlari serializer
    """
    file_url = serializers.SerializerMethodField()
    partner_name = serializers.CharField(source='partner.name', read_only=True)

    class Meta:
        model = PartnerResponseDocument
        fields = [
            'id',
            'partner_name',
            'file_name',
            'file_url',
            'title',
            'description',
            'document_type',
            'uploaded_at',
        ]

    def get_file_url(self, obj):
        """File URL"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


class PartnerPatientListSerializer(serializers.ModelSerializer):
    """
    Bemorlar ro'yxati - Hamkor paneli uchun

    ✅ Faqat ruxsat etilgan ma'lumotlar:
    - ID
    - Ism-Familiya
    - Bosqich
    - Tag
    - Oxirgi yangilanish

    ❌ MAXFIY MA'LUMOTLAR YO'Q:
    - Pasport
    - Telefon
    - Email
    - Tug'ilgan sana
    - Manzil
    """
    stage_name = serializers.CharField(source='stage.title', read_only=True)
    stage_code = serializers.CharField(source='stage.code', read_only=True)
    tag_name = serializers.CharField(source='tag.name', read_only=True, allow_null=True)
    applications_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Patient
        fields = [
            'id',
            'full_name',  # ✅ Ruxsat etilgan
            'gender',  # ✅ Ruxsat etilgan
            'stage_name',
            'stage_code',
            'tag_name',
            'applications_count',
            'created_at',
            'updated_at',
        ]
        # ❌ EXCLUDE qilingan (ko'rinmaydi):
        # passport, phone_number, email, date_of_birth, address, etc.


class PartnerPatientDetailSerializer(serializers.ModelSerializer):
    """
    Bemorning batafsil ma'lumotlari - Hamkor paneli uchun

    ✅ Faqat ruxsat etilgan ma'lumotlar:
    - Ism-Familiya
    - Tibbiy ma'lumotlar
    - Hujjatlar
    - Arizalar
    - Hamkor javoblari

    ❌ MAXFIY MA'LUMOTLAR YO'Q:
    - Pasport, telefon, email, address, tug'ilgan sana
    """
    stage_name = serializers.CharField(source='stage.title', read_only=True)
    stage_code = serializers.CharField(source='stage.code', read_only=True)
    tag_name = serializers.CharField(source='tag.name', read_only=True, allow_null=True)

    # Nested serializers
    documents = PartnerPatientDocumentSerializer(many=True, read_only=True)
    applications = PartnerApplicationSerializer(many=True, read_only=True)
    partner_responses = PartnerResponseDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Patient
        fields = [
            'id',
            'full_name',  # ✅ Ruxsat etilgan
            'gender',  # ✅ Ruxsat etilgan

            # Tibbiy ma'lumotlar (ruxsat etilgan)
            'complaints',
            'previous_diagnosis',
            'current_medications',
            'allergies',
            'chronic_diseases',

            # Bosqich va tag
            'stage_name',
            'stage_code',
            'tag_name',

            # Nested data
            'documents',
            'applications',
            'partner_responses',

            # Timestamps
            'created_at',
            'updated_at',
        ]
        # ❌ EXCLUDE qilingan (maxfiy):
        # passport, phone_number, email, date_of_birth, address,
        # created_by, contract_file, response_letter, etc.


# ===============================================================
# STAGE CHANGE SERIALIZER
# ===============================================================

class PartnerStageChangeSerializer(serializers.Serializer):
    """
    Bosqichni o'zgartirish

    Hamkor bemorni bir bosqichdan ikkinchisiga o'tkazishi mumkin.
    """
    new_stage = serializers.CharField(
        required=True,
        help_text='Yangi bosqich kodi (masalan: stage_response)'
    )

    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Izoh (tarixga yoziladi)'
    )

    def validate_new_stage(self, value):
        """Bosqich mavjudligini tekshirish"""
        try:
            stage = Stage.objects.get(code=value)
        except Stage.DoesNotExist:
            raise serializers.ValidationError(f"Bosqich '{value}' topilmadi")
        return value


# ===============================================================
# SERIALIZER: Professional optimized response upload
# ===============================================================
from rest_framework import serializers
from .models import PartnerResponseDocument


class PartnerResponseUploadSerializer(serializers.ModelSerializer):
    """
    📤 Partner fayl yuklaydi (Documents bosqichidagi bemor uchun)
    """
    file = serializers.FileField(required=True, help_text="Fayl (PDF, PNG, DOCX)")
    description = serializers.CharField(required=False, allow_blank=True, help_text="Qo‘shimcha izoh")

    class Meta:
        model = PartnerResponseDocument
        fields = ["file", "description", "title", "document_type"]

    def validate_file(self, file):
        """Fayl hajmini tekshirish (max 10MB)"""
        if file.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Fayl hajmi 10MB dan oshmasligi kerak.")
        return file

    def create(self, validated_data):
        patient = self.context.get("patient")
        partner = self.context.get("partner")
        if not patient or not partner:
            raise serializers.ValidationError("Bemor yoki hamkor aniqlanmadi.")

        document = PartnerResponseDocument.objects.create(
            patient=patient,
            partner=partner,
            **validated_data
        )
        return document

class PartnerResponseSerializer(serializers.ModelSerializer):
    """
    📄 Hamkor yuborgan javob xatini ko‘rish uchun to‘liq serializer
    """
    file_url = serializers.SerializerMethodField()
    partner_name = serializers.CharField(source="partner.name", read_only=True)
    patient_name = serializers.CharField(source="patient.full_name", read_only=True)
    patient_id = serializers.IntegerField(source="patient.id", read_only=True)  # ✅ bemor ID

    class Meta:
        model = PartnerResponseDocument
        fields = [
            "id",
            "file_url",
            "description",
            "title",
            "document_type",
            "patient_id",
            "patient_name",
            "partner_name",
            "uploaded_at",  # ✅ modeldagi haqiqiy sana
        ]

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None


# ===============================================================
# PARTNER PROFILE SERIALIZER
# ===============================================================

class PartnerProfileSerializer(serializers.ModelSerializer):
    """
    Hamkor profili

    Hamkor o'z profil ma'lumotlarini ko'rishi uchun.
    """
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Partner
        fields = [
            'id',
            'username',
            'email',
            'name',
            'avatar',
            'avatar_url',
            'code',
            'specialization',
            'contact_person',
            'phone',
            'total_patients',
            'active_patients',
            'is_active',
            'created_at',
        ]
        read_only_fields = [
            'code',
            'total_patients',
            'active_patients',
            'created_at',
            'avatar_url',
        ]
        extra_kwargs = {
            'avatar': {'write_only': True},
        }

    def get_avatar_url(self, obj):
        """Avatar URL qaytarish"""
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None


# ===============================================================
# OPERATOR-PARTNER CONVERSATION SERIALIZERS
# ===============================================================

from .models import (
    OperatorPartnerConversation,
    OperatorPartnerMessage,
    OperatorPartnerAttachment
)
from django.contrib.auth import get_user_model

User = get_user_model()


class OperatorMinimalSerializer(serializers.ModelSerializer):
    """Operator minimal ma'lumotlari"""
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'full_name', 'phone_number']

    def get_full_name(self, obj):
        """To'liq ism"""
        if hasattr(obj, 'get_full_name') and callable(obj.get_full_name):
            return obj.get_full_name()
        return obj.phone_number


class PartnerMinimalSerializer(serializers.ModelSerializer):
    """Partner minimal ma'lumotlari"""

    class Meta:
        from .models import Partner
        model = Partner
        fields = ['id', 'name', 'code', 'specialization']


class OperatorPartnerAttachmentSerializer(serializers.ModelSerializer):
    """Operator-Partner fayl serializer"""
    file_url = serializers.SerializerMethodField()
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = OperatorPartnerAttachment
        fields = [
            'id',
            'file',
            'file_url',
            'file_type',
            'mime_type',
            'size',
            'formatted_size',
            'original_name',
            'uploaded_by',
            'uploaded_by_name',
            'uploaded_at',
        ]
        read_only_fields = [
            'id',
            'file_url',
            'file_type',
            'mime_type',
            'size',
            'formatted_size',
            'original_name',
            'uploaded_by',
            'uploaded_by_name',
            'uploaded_at',
        ]
        extra_kwargs = {
            'file': {'write_only': True}
        }

    def get_file_url(self, obj):
        """Fayl URL"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

    def get_uploaded_by_name(self, obj):
        """Yuklagan foydalanuvchi ismi"""
        if obj.uploaded_by:
            return obj.uploaded_by.get_full_name()
        return None


class OperatorPartnerMessageSerializer(serializers.ModelSerializer):
    """Operator-Partner xabar serializer"""
    sender_name = serializers.SerializerMethodField()
    sender_role = serializers.SerializerMethodField()
    attachments = OperatorPartnerAttachmentSerializer(many=True, read_only=True)
    reply_to_message = serializers.SerializerMethodField()

    class Meta:
        model = OperatorPartnerMessage
        fields = [
            'id',
            'conversation',
            'sender',
            'sender_name',
            'sender_role',
            'type',
            'content',
            'reply_to',
            'reply_to_message',
            'attachments',
            'created_at',
            'edited_at',
            'is_deleted',
            'is_read',
        ]
        read_only_fields = [
            'id',
            'sender',
            'sender_name',
            'sender_role',
            'created_at',
            'edited_at',
            'is_deleted',
            'is_read',
            'reply_to_message',
        ]

    def get_sender_name(self, obj):
        """Yuboruvchi ismi"""
        if obj.sender:
            return obj.sender.get_full_name()
        return None

    def get_sender_role(self, obj):
        """Yuboruvchi roli"""
        if obj.sender:
            return getattr(obj.sender, 'role', 'unknown')
        return None

    def get_reply_to_message(self, obj):
        """Javob berilyotgan xabar"""
        if obj.reply_to:
            return {
                'id': obj.reply_to.id,
                'content': obj.reply_to.content,
                'sender_name': obj.reply_to.sender.get_full_name() if obj.reply_to.sender else None,
                'created_at': obj.reply_to.created_at,
            }
        return None


class OperatorPartnerConversationSerializer(serializers.ModelSerializer):
    """Operator-Partner suhbat serializer (to'liq)"""
    operator_name = serializers.SerializerMethodField()
    partner_info = PartnerMinimalSerializer(source='partner', read_only=True)
    messages = OperatorPartnerMessageSerializer(many=True, read_only=True)
    unread_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = OperatorPartnerConversation
        fields = [
            'id',
            'operator',
            'operator_name',
            'partner',
            'partner_info',
            'title',
            'is_active',
            'created_by',
            'last_message_at',
            'last_message',
            'unread_count',
            'messages',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'operator_name',
            'partner_info',
            'created_by',
            'last_message_at',
            'last_message',
            'unread_count',
            'messages',
            'created_at',
            'updated_at',
        ]

    def get_operator_name(self, obj):
        """Operator ismi"""
        if obj.operator:
            return obj.operator.get_full_name()
        return None

    def get_unread_count(self, obj):
        """O'qilmagan xabarlar soni"""
        request = self.context.get('request')
        if not request or not request.user:
            return 0

        return obj.messages.filter(
            is_read=False,
            is_deleted=False
        ).exclude(sender=request.user).count()

    def get_last_message(self, obj):
        """Oxirgi xabar"""
        last_msg = obj.messages.filter(is_deleted=False).order_by('-created_at').first()
        if last_msg:
            return {
                'id': last_msg.id,
                'content': last_msg.content,
                'sender_name': last_msg.sender.get_full_name() if last_msg.sender else None,
                'type': last_msg.type,
                'created_at': last_msg.created_at,
            }
        return None


class OperatorPartnerConversationListSerializer(serializers.ModelSerializer):
    """Operator-Partner suhbatlar ro'yxati serializer"""
    operator_name = serializers.SerializerMethodField()
    partner_info = PartnerMinimalSerializer(source='partner', read_only=True)
    unread_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = OperatorPartnerConversation
        fields = [
            'id',
            'operator',
            'operator_name',
            'partner',
            'partner_info',
            'title',
            'is_active',
            'last_message_at',
            'last_message',
            'unread_count',
            'created_at',
        ]

    def get_operator_name(self, obj):
        """Operator ismi"""
        if obj.operator:
            return obj.operator.get_full_name()
        return None

    def get_unread_count(self, obj):
        """O'qilmagan xabarlar soni"""
        request = self.context.get('request')
        if not request or not request.user:
            return 0

        return obj.messages.filter(
            is_read=False,
            is_deleted=False
        ).exclude(sender=request.user).count()

    def get_last_message(self, obj):
        """Oxirgi xabar"""
        last_msg = obj.messages.filter(is_deleted=False).order_by('-created_at').first()
        if last_msg:
            return {
                'id': last_msg.id,
                'content': last_msg.content[:50] + '...' if len(last_msg.content) > 50 else last_msg.content,
                'sender_name': last_msg.sender.get_full_name() if last_msg.sender else None,
                'type': last_msg.type,
                'created_at': last_msg.created_at,
            }
        return None


class OperatorPartnerMessageCreateSerializer(serializers.ModelSerializer):
    """Xabar yaratish serializer"""

    class Meta:
        model = OperatorPartnerMessage
        fields = [
            'conversation',
            'content',
            'reply_to',
            'type',
        ]

    def validate_conversation(self, value):
        """Suhbat faol ekanligini tekshirish"""
        if not value.is_active:
            raise serializers.ValidationError("Suhbat faol emas")
        return value

    def create(self, validated_data):
        """Xabar yaratish"""
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("Foydalanuvchi aniqlanmadi")

        # Xabarni yaratish
        message = OperatorPartnerMessage.objects.create(
            sender=request.user,
            **validated_data
        )

        # Suhbatning last_message_at ni yangilash
        conversation = validated_data['conversation']
        conversation.last_message_at = message.created_at
        conversation.save(update_fields=['last_message_at'])

        return message

    def to_representation(self, instance):
        """Response formatini to'g'rilash"""
        return OperatorPartnerMessageSerializer(instance, context=self.context).data

