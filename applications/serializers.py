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


# 🧾 Arizalar ro‘yxati / tafsilot
class ApplicationSerializer(serializers.ModelSerializer):
    patient = serializers.PrimaryKeyRelatedField(queryset=Patient.objects.all(), required=True)
    stage = StageSerializer(read_only=True)
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


# ✍️ Ariza yaratish / yangilash
class ApplicationCreateUpdateSerializer(serializers.ModelSerializer):
    stage = serializers.PrimaryKeyRelatedField(queryset=Stage.objects.all(), required=False)
    patient = serializers.PrimaryKeyRelatedField(queryset=Patient.objects.all(), required=True)

    class Meta:
        model = Application
        fields = [
            "patient", "clinic_name", "complaint", "diagnosis",
            "final_conclusion", "stage", "status", "comment"
        ]

    def create(self, validated_data):
        request = self.context.get("request")
        application = Application.objects.create(**validated_data)
        # tarixga yozuv
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
