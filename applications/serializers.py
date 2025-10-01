from patients.models import Patient
from rest_framework import serializers
from .models import Application, Document
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'phone_number', 'first_name', 'last_name']  # Adjust fields as needed

class ApplicationSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    patient = UserSerializer(read_only=True)  # Include user details in the response
    patient_id = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = [
            "id",
            "application_id",
            "patient",        # User ma'lumotlari
            "clinic_name",
            "complaint",
            "diagnosis",
            "status",
            "status_display",
            "created_at",
            "updated_at",
            "patient_id",     # Patient.id qo‘shildi
        ]
        read_only_fields = [
            "application_id",
            "status",
            "created_at",
            "updated_at",
            "patient",
            "patient_id",
        ]

    def get_patient_id(self, obj):
        # Application.patient -> CustomUser
        patient = Patient.objects.filter(profile__user=obj.patient).first()
        return patient.id if patient else None

    def create(self, validated_data):
        request = self.context.get("request")
        validated_data["patient"] = request.user
        return super().create(validated_data)

class DocumentSerializer(serializers.ModelSerializer):
    application = serializers.PrimaryKeyRelatedField(queryset=Application.objects.all())
    class Meta:
        model = Document
        fields = ["id", "application", "file", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]