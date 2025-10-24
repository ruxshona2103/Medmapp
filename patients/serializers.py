from rest_framework import serializers
from core.models import Stage, Tag
from .models import Patient, PatientHistory, PatientDocument, ChatMessage, Contract
import os


# ===============================================================
# 📎 PATIENT DOCUMENT SERIALIZER
# ===============================================================
class PatientDocumentSerializer(serializers.ModelSerializer):
    """Bemor hujjatlari"""
    uploaded_by = serializers.StringRelatedField(read_only=True)
    file_url = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()

    class Meta:
        model = PatientDocument
        fields = ["id", "file", "file_url", "file_name", "description", "uploaded_by", "uploaded_at"]
        read_only_fields = ["uploaded_by", "uploaded_at", "file_url", "file_name"]
        ref_name = "PatientDocumentSerializer"

    def get_file_url(self, obj):
        """To'liq URL"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

    def get_file_name(self, obj):
        """Fayl nomi"""
        if obj.file:
            return os.path.basename(obj.file.name)
        return None


# ===============================================================
# 🕓 PATIENT HISTORY SERIALIZER
# ===============================================================
class PatientHistorySerializer(serializers.ModelSerializer):
    """Bemor tarixi"""
    author = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = PatientHistory
        fields = ["id", "author", "comment", "created_at"]
        ref_name = "PatientHistorySerializer"


# ===============================================================
# 📋 PATIENT LIST SERIALIZER - Kanban/list uchun
# ===============================================================
class PatientListSerializer(serializers.ModelSerializer):
    """Bemorlar ro'yxati - Kanban board uchun (faqat minimal ma'lumotlar)"""
    stage_id = serializers.IntegerField(source='stage.id', read_only=True, allow_null=True)
    tag_id = serializers.IntegerField(source='tag.id', read_only=True, allow_null=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = [
            "id",
            "full_name",
            "gender",
            "phone_number",
            "email",
            "stage_id",
            "tag_id",
            "avatar",
            "avatar_url",
            "created_at",
        ]
        ref_name = "PatientListSerializer"

    def get_avatar_url(self, obj):
        """Avatar to'liq URL"""
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None


# ===============================================================
# 🔹 PATIENT DETAIL SERIALIZER - To'liq ma'lumotlar
# ===============================================================
class PatientDetailSerializer(serializers.ModelSerializer):
    """Bemor to'liq ma'lumotlari - history, documents va applications bilan"""
    stage_id = serializers.IntegerField(source='stage.id', read_only=True, allow_null=True)
    tag_id = serializers.IntegerField(source='tag.id', read_only=True, allow_null=True)
    stage = serializers.SerializerMethodField()
    tag = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()
    documents = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    applications = serializers.SerializerMethodField()
    total_applications = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = [
            "id",
            "full_name",
            "date_of_birth",
            "gender",
            "phone_number",
            "email",
            "complaints",
            "previous_diagnosis",
            "stage_id",
            "stage",
            "tag_id",
            "tag",
            "avatar",
            "avatar_url",
            "created_at",
            "updated_at",
            "history",
            "documents",
            "applications",
            "total_applications",
        ]
        ref_name = "PatientDetailSerializer"

    def get_stage(self, obj):
        """Stage to'liq ma'lumot"""
        if obj.stage:
            return {
                "id": obj.stage.id,
                "title": obj.stage.title,
                "order": obj.stage.order
            }
        return None

    def get_tag(self, obj):
        """Tag to'liq ma'lumot"""
        if obj.tag:
            return {
                "id": obj.tag.id,
                "name": obj.tag.name
            }
        return None

    def get_avatar_url(self, obj):
        """Avatar to'liq URL"""
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None

    def get_history(self, obj):
        """Bemor tarixi"""
        history_items = PatientHistory.objects.filter(patient=obj).select_related('author').order_by('-created_at')[:20]
        return PatientHistorySerializer(history_items, many=True).data

    def get_documents(self, obj):
        """Bemor hujjatlari"""
        documents = PatientDocument.objects.filter(patient=obj).order_by('-uploaded_at')
        return PatientDocumentSerializer(documents, many=True, context=self.context).data

    def get_applications(self, obj):
        """Bemorning arizalari - documents bilan"""
        try:
            from applications.models import Application
            from applications.serializers import ApplicationSerializer

            applications = Application.objects.filter(
                patient=obj,
                is_archived=False
            ).select_related('stage').prefetch_related('documents').order_by('-created_at')

            return ApplicationSerializer(applications, many=True, context=self.context).data
        except Exception as e:
            return []

    def get_total_applications(self, obj):
        """Jami arizalar soni"""
        try:
            from applications.models import Application
            return Application.objects.filter(patient=obj, is_archived=False).count()
        except:
            return 0


# ===============================================================
# ✏️ PATIENT CREATE/UPDATE SERIALIZER
# ===============================================================
class PatientCreateUpdateSerializer(serializers.ModelSerializer):
    """Bemor yaratish va tahrirlash - Swagger'da rasm yuklash ko'rinadi"""
    avatar = serializers.ImageField(required=False, allow_null=True)
    stage_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    tag_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    # Response uchun
    stage = serializers.SerializerMethodField(read_only=True)
    tag = serializers.SerializerMethodField(read_only=True)
    avatar_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Patient
        fields = [
            "id",
            "full_name",
            "date_of_birth",
            "gender",
            "phone_number",
            "email",
            "complaints",
            "previous_diagnosis",
            "avatar",
            "avatar_url",
            "stage_id",
            "stage",
            "tag_id",
            "tag",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "avatar_url", "stage", "tag"]
        ref_name = "PatientCreateUpdateSerializer"

    def validate_stage_id(self, value):
        """Stage mavjudligini tekshirish"""
        if value and not Stage.objects.filter(id=value).exists():
            raise serializers.ValidationError("Stage topilmadi")
        return value

    def validate_tag_id(self, value):
        """Tag mavjudligini tekshirish"""
        if value and not Tag.objects.filter(id=value).exists():
            raise serializers.ValidationError("Tag topilmadi")
        return value

    def create(self, validated_data):
        """Yangi bemor yaratish"""
        stage_id = validated_data.pop('stage_id', None)
        tag_id = validated_data.pop('tag_id', None)

        patient = Patient.objects.create(**validated_data)

        # Stage va Tag qo'shish
        if stage_id:
            patient.stage = Stage.objects.get(id=stage_id)
        if tag_id:
            patient.tag = Tag.objects.get(id=tag_id)

        patient.save()
        return patient

    def update(self, instance, validated_data):
        """Bemorni yangilash"""
        stage_id = validated_data.pop('stage_id', None)
        tag_id = validated_data.pop('tag_id', None)

        # Stage va Tag yangilash
        if stage_id is not None:
            instance.stage = Stage.objects.get(id=stage_id) if stage_id else None
        if tag_id is not None:
            instance.tag = Tag.objects.get(id=tag_id) if tag_id else None

        # Boshqa maydonlarni yangilash
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance

    def get_stage(self, obj):
        """Stage to'liq ma'lumot"""
        if obj.stage:
            return {
                "id": obj.stage.id,
                "title": obj.stage.title,
                "order": obj.stage.order
            }
        return None

    def get_tag(self, obj):
        """Tag to'liq ma'lumot"""
        if obj.tag:
            return {
                "id": obj.tag.id,
                "name": obj.tag.name
            }
        return None

    def get_avatar_url(self, obj):
        """Avatar to'liq URL"""
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None


# ===============================================================
# 💬 CHAT MESSAGE SERIALIZER
# ===============================================================
class ChatMessageSerializer(serializers.ModelSerializer):
    """Chat xabarlari"""
    sender = serializers.StringRelatedField(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = ["id", "sender", "message", "file", "file_url", "timestamp"]
        read_only_fields = ["id", "timestamp", "sender", "file_url"]
        ref_name = "PatientChatMessageSerializer"

    def get_file_url(self, obj):
        """File to'liq URL"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


# ===============================================================
# 👤 PATIENT PROFILE SERIALIZER - Frontend profil sozlamalari uchun
# ===============================================================
class PatientProfileSerializer(serializers.ModelSerializer):
    """Bemor profili - frontend profil sozlamalari uchun"""
    stage_id = serializers.IntegerField(source='stage.id', read_only=True, allow_null=True)
    tag_id = serializers.IntegerField(source='tag.id', read_only=True, allow_null=True)
    avatar = serializers.ImageField(required=False, allow_null=True)
    avatar_url = serializers.SerializerMethodField()
    stage = serializers.SerializerMethodField()
    tag = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = [
            "id",
            "full_name",
            "date_of_birth",
            "gender",
            "phone_number",
            "email",
            "complaints",
            "previous_diagnosis",
            "stage_id",
            "stage",
            "tag_id",
            "tag",
            "avatar",
            "avatar_url",
            "created_at",
            "updated_at",
        ]
        ref_name = "PatientProfileSerializer"

    def get_avatar_url(self, obj):
        """Avatar to'liq URL"""
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None

    def get_stage(self, obj):
        """Stage to'liq ma'lumot"""
        if obj.stage:
            return {
                "id": obj.stage.id,
                "title": obj.stage.title,
                "order": obj.stage.order
            }
        return None

    def get_tag(self, obj):
        """Tag to'liq ma'lumot"""
        if obj.tag:
            return {
                "id": obj.tag.id,
                "name": obj.tag.name
            }
        return None