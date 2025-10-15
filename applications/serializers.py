from rest_framework import serializers
from django.contrib.auth import get_user_model
from core.models import Stage
from core.serializers import StageSerializer
from .models import Application, Document, ApplicationHistory
from patients.models import Patient

User = get_user_model()


# 👤 Minimal User ma'lumot
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "phone_number", "first_name", "last_name"]


# 🕓 Ariza tarixi
class ApplicationHistorySerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)

    class Meta:
        model = ApplicationHistory
        fields = ["id", "author", "comment", "created_at"]
        read_only_fields = ["id", "author", "created_at"]


# 📎 Hujjatlar
class DocumentSerializer(serializers.ModelSerializer):
    uploaded_by = UserSerializer(read_only=True)

    class Meta:
        model = Document
        fields = ["id", "application", "file", "description", "uploaded_by", "uploaded_at"]
        read_only_fields = ["id", "uploaded_by", "uploaded_at", "application"]

from rest_framework import serializers
from .models import Application, ApplicationHistory, Document
from core.models import Stage
from patients.models import Patient


# 🧾 Ariza tarixi serializer
class ApplicationHistorySerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = ApplicationHistory
        fields = ["id", "author_name", "comment", "created_at"]

    def get_author_name(self, obj):
        return getattr(obj.author, "get_full_name", lambda: str(obj.author))()


# 📎 Hujjat serializer
class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["id", "file", "description", "uploaded_at"]


# 🔹 Ariza asosiy serializer
class ApplicationSerializer(serializers.ModelSerializer):
    patient = serializers.PrimaryKeyRelatedField(queryset=Patient.objects.all(), required=True)
    stage = serializers.SerializerMethodField()
    documents = DocumentSerializer(many=True, read_only=True)
    history = ApplicationHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Application
        fields = [
            "id", "application_id", "patient", "clinic_name",
            "complaint", "diagnosis", "final_conclusion",
            "stage", "status", "comment", "created_at",
            "updated_at", "is_archived", "documents", "history"
        ]
        read_only_fields = [
            "id", "application_id", "created_at", "updated_at",
            "documents", "history", "is_archived"
        ]

    def get_stage(self, obj):
        return getattr(obj.stage, "title", None)


# ✍️ Ariza yaratish / yangilash serializer
class ApplicationCreateUpdateSerializer(serializers.ModelSerializer):
    stage = serializers.PrimaryKeyRelatedField(queryset=Stage.objects.all(), required=False)
    patient = serializers.PrimaryKeyRelatedField(queryset=Patient.objects.all(), required=True)
    application_id = serializers.CharField(read_only=True)  # natijada ko‘rsatish uchun qo‘shildi

    class Meta:
        model = Application
        fields = [
            "id", "application_id", "patient", "clinic_name", "complaint",
            "diagnosis", "final_conclusion", "stage", "status", "comment"
        ]

    def create(self, validated_data):
        request = self.context.get("request")
        application = Application.objects.create(**validated_data)
        ApplicationHistory.objects.create(
            application=application,
            author=getattr(request, "user", None),
            comment="📝 Yangi ariza yaratildi"
        )
        return application

    def update(self, instance, validated_data):
        request = self.context.get("request")
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        ApplicationHistory.objects.create(
            application=instance,
            author=getattr(request, "user", None),
            comment="🪶 Ariza maʼlumotlari yangilandi"
        )
        return instance


# -------------------------------------------OPERATOR PANELI------------------------------------------------------------
from rest_framework import serializers
from .models import Application
from patients.models import Patient


class CompletedApplicationSerializer(serializers.ModelSerializer):
    """✅ Tugallangan va rad etilgan murojaatlar uchun serializer"""

    patient_name = serializers.CharField(source="patient.full_name", read_only=True)
    phone_number = serializers.CharField(source="patient.phone_number", read_only=True)
    clinic = serializers.CharField(source="clinic_name", read_only=True)
    final_conclusion = serializers.CharField(read_only=True)
    status_label = serializers.SerializerMethodField()
    date = serializers.DateField(source="updated_at", format="%Y-%m-%d", read_only=True)

    class Meta:
        model = Application
        fields = [
            "id",
            "application_id",
            "patient_name",
            "phone_number",
            "final_conclusion",
            "clinic",
            "date",
            "status",
            "status_label",
        ]

    def get_status_label(self, obj):
        """Frontend uchun rangli badge nomini qaytaradi"""
        if obj.status == "completed":
            return "Tugatilgan"
        elif obj.status == "rejected":
            return "Rad etilgan"
        return "Boshqa"
