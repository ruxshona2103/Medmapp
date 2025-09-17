# patients/serializers.py
from django.utils.autoreload import logger
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator, EmailValidator
from .models import (
    PatientProfile,
    Stage,
    Tag,
    PatientHistory,
    PatientDocument,
    ChatMessage,
    Contract,
)

User = get_user_model()


# ---- CustomUser uchun xavfsiz serializer (faqat kerakli maydonlar) ----
class PatientUserSerializer(serializers.ModelSerializer):
    """
    Bemor, operator, doctor, admin ma'lumotlari uchun ommaviy serializer.
    Faqat maxfiy emas maydonlar.
    """

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'role', 'phone_number']
        read_only_fields = ['id']


# ---------- Asosiy Model Serializers ----------
class StageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stage
        fields = ['id', 'title', 'code_name', 'order', 'color']
        read_only_fields = ['id', 'order']


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'color']
        read_only_fields = ['id']


# ---------- Bog'langan Ma'lumotlar ----------
class PatientHistorySerializer(serializers.ModelSerializer):
    author = PatientUserSerializer(read_only=True)

    class Meta:
        model = PatientHistory
        fields = ['id', 'author', 'comment', 'created_at']
        read_only_fields = ['id', 'created_at']


class PatientDocumentSerializer(serializers.ModelSerializer):
    uploaded_by = PatientUserSerializer(read_only=True)

    class Meta:
        model = PatientDocument
        fields = ['id', 'file', 'description', 'uploaded_by', 'uploaded_at', 'source_type']
        read_only_fields = ['id', 'uploaded_at', 'uploaded_by']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if instance.file and request:
            try:
                data['file'] = request.build_absolute_uri(instance.file.url)
            except Exception:
                data['file'] = None
        return data


class ChatMessageSerializer(serializers.ModelSerializer):
    sender = PatientUserSerializer(read_only=True)

    class Meta:
        model = ChatMessage
        fields = ['id', 'sender', 'message', 'file', 'timestamp']
        read_only_fields = ['id', 'timestamp', 'sender']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if instance.file and request:
            try:
                data['file'] = request.build_absolute_uri(instance.file.url)
            except Exception:
                data['file'] = None
        return data


# ---------- PatientProfile Serializers ----------
class PatientAvatarUploadSerializer(serializers.ModelSerializer):
    """
    Avatar yuklash uchun faqat avatar maydoni.
    """

    class Meta:
        model = PatientProfile
        fields = ["avatar"]


class PatientProfileCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Yangilash uchun serializer. Operator ham bemor ham ishlatadi.
    """
    stage = serializers.PrimaryKeyRelatedField(
        queryset=Stage.objects.all(),
        required=False,
        allow_null=True
    )
    tag = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        required=False,
        allow_null=True
    )

    class Meta:
        model = PatientProfile
        fields = [
            'full_name', 'passport', 'dob', 'gender',
            'phone', 'email', 'stage', 'tag'
        ]

    def validate_phone(self, value):
        validator = RegexValidator(
            regex=r'^\+998\d{9}$',
            message="Telefon raqam +998XXXXXXXXX formatida bo'lishi kerak."
        )
        validator(value)
        return value

    def validate_email(self, value):
        if value and not value.strip():
            raise serializers.ValidationError("Email bo'sh bo'lmasligi kerak.")
        return value

    def validate_full_name(self, value):
        if not value or len(value.strip()) < 2:
            raise serializers.ValidationError("To'liq ism kamida 2 ta belgi bo'lishi kerak.")
        return value.strip()


class PatientProfileSerializer(serializers.ModelSerializer):
    """
    To'liq profil ma'lumotlari (GET).
    """
    user = PatientUserSerializer(read_only=True)
    created_by = PatientUserSerializer(read_only=True)
    avatar_url = serializers.SerializerMethodField()

    # Bog'langan ma'lumotlar
    history = PatientHistorySerializer(many=True, read_only=True)
    documents = PatientDocumentSerializer(many=True, read_only=True)
    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta:
        model = PatientProfile
        fields = [
            'id', 'user', 'created_by', 'full_name', 'passport', 'dob', 'gender',
            'phone', 'email', 'avatar_url', 'created_at', 'updated_at',
            'history', 'documents', 'messages'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'user', 'created_by', 'avatar_url',
            'history', 'documents', 'messages'
        ]

    def get_avatar_url(self, obj):
        request = self.context.get("request")
        if hasattr(obj, "avatar") and obj.avatar and request:
            try:
                return request.build_absolute_uri(obj.avatar.url)
            except Exception:
                return None
        return None


class PatientProfileWithDocumentsSerializer(serializers.ModelSerializer):
    """
    Response Letters sahifasi uchun — faqat partner hujjatlari.
    """
    user = PatientUserSerializer(read_only=True)
    created_by = PatientUserSerializer(read_only=True)
    documents = serializers.SerializerMethodField()

    class Meta:
        model = PatientProfile
        fields = ['id', 'user', 'created_by', 'full_name', 'phone', 'documents']

    def get_documents(self, obj):
        partner_docs = obj.documents.filter(source_type='partner')
        return PatientDocumentSerializer(partner_docs, many=True, context=self.context).data


class ContractSerializer(serializers.ModelSerializer):
    """
    Shartnoma ma'lumotlari.
    """
    patient_profile = PatientProfileSerializer(read_only=True)
    approved_by = PatientUserSerializer(read_only=True)

    class Meta:
        model = Contract
        fields = ['id', 'patient_profile', 'file', 'status', 'approved_by', 'approved_at']
        read_only_fields = ['id', 'patient_profile', 'approved_by', 'approved_at']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if instance.file and request:
            try:
                data['file'] = request.build_absolute_uri(instance.file.url)
            except Exception:
                data['file'] = None
        return data

class CustomUserForPatientCreateSerializer(serializers.ModelSerializer):
    """
    Operator tomonidan bemor yaratishda foydalanuvchi ma'lumotlari.
    """
    class Meta:
        model = User
        fields = ['phone_number', 'first_name', 'last_name']

    def validate_phone_number(self, value):
        if not value.startswith('+998') or len(value) != 13:
            raise serializers.ValidationError("Telefon raqam +998XXXXXXXXX formatida bo'lishi kerak.")
        return value


class OperatorPatientCreateSerializer(serializers.ModelSerializer):
    """
    Operator tomonidan yangi bemor yaratish uchun.
    - Yangi CustomUser yaratiladi (agar mavjud bo'lmasa)
    - PatientProfile yaratiladi
    """
    user = CustomUserForPatientCreateSerializer(write_only=True)

    class Meta:
        model = PatientProfile
        fields = [
            'user',
            'full_name', 'passport', 'dob', 'gender',
            'phone', 'email', 'stage', 'tag'
        ]

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        phone = user_data['phone_number'].strip()

        # 1. Telefon raqam bo'yicha foydalanuvchini topish yoki yaratish
        user, created = User.objects.get_or_create(
            phone_number=phone,
            defaults={
                'first_name': user_data.get('first_name'),
                'last_name': user_data.get('last_name'),
                'role': 'user',  # bemor sifatida
                'is_active': True,
            }
        )

        # Agar yangi yaratilgan bo'lsa — parol o'rnatish (masalan: oxirgi 6 ta raqam)
        if created:
            raw_password = phone[-6:]  # +998901234567 → 234567
            user.set_password(raw_password)
            user.save()
            logger.info(f"Yangi bemor foydalanuvchisi yaratildi: {phone}")

        # 2. PatientProfile yaratish
        profile = PatientProfile.objects.create(user=user, **validated_data)
        return profile