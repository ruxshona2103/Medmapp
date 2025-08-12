from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    PatientProfile, Application, Document, Service,
    OrderedService, ServiceStatusHistory
)

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name", "email", "is_staff")
        read_only_fields = ("id", "is_staff")

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ("id", "file", "uploaded_at")
        read_only_fields = ("id", "uploaded_at")

class PatientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientProfile
        fields = ("fullName", "passport", "dob", "gender", "phone", "email")

class PatientSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    patient_profile = PatientProfileSerializer(read_only=True)

    class Meta:
        model = PatientProfile
        fields = ("id", "user", "patient_profile", "created_at")
        read_only_fields = ("id", "created_at")


class ApplicationSerializer(serializers.ModelSerializer):
    patient_profile = PatientProfileSerializer(source="patient.patient_profile", read_only=True)
    documents = DocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Application
        fields = (
            "id", "patient_profile", "complaint", "diagnosis",
            "status", "created_at", "documents"
        )
        read_only_fields = ("id", "status", "created_at", "documents", "patient_profile")

class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = (
            "service_id", "name", "description",
            "price", "price_description", "icon_class"
        )


class ServiceStatusHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceStatusHistory
        fields = ("id", "status_text", "date")
        read_only_fields = ("id", "date")



class OrderedServiceSerializer(serializers.ModelSerializer):
    service = ServiceSerializer(read_only=True)
    status_history = ServiceStatusHistorySerializer(many=True, read_only=True)

    class Meta:
        model = OrderedService
        fields = (
            "id", "application", "service",
            "order_date", "data", "current_status_index", "status_history"
        )
        read_only_fields = ("id", "application", "order_date", "status_history")
