from rest_framework import serializers
from core.models import Stage, Tag
from .models import Patient, PatientHistory, PatientDocument, ChatMessage, Contract


# --- Oddiy helper serializerlar ---
class PatientDocumentSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = PatientDocument
        fields = ["id", "file", "description", "uploaded_by", "uploaded_at"]
        read_only_fields = ["uploaded_by", "uploaded_at"]
        ref_name = "PatientDocumentSerializer"


class PatientHistorySerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = PatientHistory
        fields = ["id", "author", "comment", "created_at"]
        ref_name = "PatientHistorySerializer"


# === Kanban/list ko'rinishi: faqat ID’lar ===
class PatientListSerializer(serializers.ModelSerializer):
    stage_id = serializers.IntegerField(read_only=True, allow_null=True)
    tag_id = serializers.IntegerField(read_only=True, allow_null=True)

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
            "avatar",  # 🆕 qo‘shildi
            "created_at",
        ]
        ref_name = "PatientListSerializer"


# === Batafsil ko'rinish ===
class PatientDetailSerializer(serializers.ModelSerializer):
    stage_id = serializers.IntegerField(read_only=True, allow_null=True)
    tag_id = serializers.IntegerField(read_only=True, allow_null=True)
    history = PatientHistorySerializer(many=True, read_only=True)
    documents = PatientDocumentSerializer(many=True, read_only=True)

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
            "tag_id",
            "avatar",  # 🆕 qo‘shildi
            "created_at",
            "updated_at",
            "history",
            "documents",
        ]
        ref_name = "PatientDetailSerializer"


# === Create/Update serializer (Swagger’da rasm yuklash chiqadi) ===
class PatientCreateUpdateSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(required=False, allow_null=True)  # 🆕

    class Meta:
        model = Patient
        fields = [
            "full_name",
            "date_of_birth",
            "gender",
            "phone_number",
            "passport",
            "email",
            "complaints",
            "previous_diagnosis",
            "avatar",  # 🆕 shu joyda Swagger’da upload chiqadi
            "tag",
            "stage",
        ]
        ref_name = "PatientCreateUpdateSerializer"


class ChatMessageSerializer(serializers.ModelSerializer):
    sender = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = ChatMessage
        fields = ["id", "sender", "message", "file", "timestamp"]
        read_only_fields = ["id", "timestamp", "sender"]
        ref_name = "PatientChatMessageSerializer"


# === Bemorga mo'ljallangan profil (frontenddagi profil sozlamalari uchun) ===
class PatientProfileSerializer(serializers.ModelSerializer):
    stage_id = serializers.IntegerField(read_only=True, allow_null=True)
    tag_id = serializers.IntegerField(read_only=True, allow_null=True)
    avatar = serializers.ImageField(required=False, allow_null=True)  # 🆕 qo‘shildi

    class Meta:
        model = Patient
        fields = [
            "id",
            "full_name",
            "date_of_birth",
            "gender",
            "passport",
            "phone_number",
            "email",
            "complaints",
            "previous_diagnosis",
            "stage_id",
            "tag_id",
            "avatar",
            "created_at",
            "updated_at",
        ]
        ref_name = "PatientProfileSerializer"
