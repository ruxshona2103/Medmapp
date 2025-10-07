from rest_framework import serializers
from core.models import Stage, Tag
from .models import Patient, PatientHistory, PatientDocument, ChatMessage, Contract


# --- Nested core serializers (unique ref_name) ---
class PatientStageSerializer(serializers.ModelSerializer):
    """Bemorlar uchun bosqich ma'lumotlari (Kanban)"""
    class Meta:
        model = Stage
        fields = ["id", "title", "order", "color"]
        ref_name = "PatientStageSerializer"


class PatientTagSerializer(serializers.ModelSerializer):
    """Bemorlar uchun teg (holat) ma'lumotlari"""
    class Meta:
        model = Tag
        fields = ["id", "name", "color"]
        ref_name = "PatientTagSerializer"


class PatientDocumentSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = PatientDocument
        fields = ["id", "file", "description", "uploaded_by", "uploaded_at", "source_type"]
        read_only_fields = ["uploaded_by", "uploaded_at"]
        ref_name = "PatientDocumentSerializer"


class PatientHistorySerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = PatientHistory
        fields = ["id", "author", "comment", "created_at"]
        ref_name = "PatientHistorySerializer"


class PatientListSerializer(serializers.ModelSerializer):
    stage = PatientStageSerializer(read_only=True)
    tag = PatientTagSerializer(read_only=True)

    class Meta:
        model = Patient
        fields = ["id", "full_name", "gender", "phone_number", "email", "stage", "tag", "created_at"]
        ref_name = "PatientListSerializer"


class PatientDetailSerializer(serializers.ModelSerializer):
    stage = PatientStageSerializer(read_only=True)
    tag = PatientTagSerializer(read_only=True)
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
            "source",
            "stage",
            "tag",
            "created_at",
            "updated_at",
            "history",
            "documents",
        ]
        ref_name = "PatientDetailSerializer"


class PatientCreateUpdateSerializer(serializers.ModelSerializer):
    """Yaratish/Yangilash uchun serializer"""
    class Meta:
        model = Patient
        fields = [
            "full_name","date_of_birth","gender","phone_number","email",
            "complaints","previous_diagnosis","source","tag","stage",
        ]
        ref_name = "PatientCreateUpdateSerializer"


class ChatMessageSerializer(serializers.ModelSerializer):
    sender = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = ChatMessage
        fields = ["id", "sender", "message", "file", "timestamp"]
        read_only_fields = ["id", "timestamp", "sender"]
        ref_name = "PatientChatMessageSerializer"


class PatientProfileSerializer(serializers.ModelSerializer):
    stage = PatientStageSerializer(read_only=True)
    tag = PatientTagSerializer(read_only=True)

    class Meta:
        model = Patient
        fields = [
            "id","full_name","date_of_birth","gender","phone_number","email",
            "complaints","previous_diagnosis","source","stage","tag",
            "created_at","updated_at",
        ]
        ref_name = "PatientProfileSerializer"
