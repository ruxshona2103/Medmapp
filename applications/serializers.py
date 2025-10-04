from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Application, Document, ApplicationHistory
from stages.serializers import StageSerializer

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'phone_number', 'first_name', 'last_name']

class ApplicationHistorySerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    class Meta:
        model = ApplicationHistory
        fields = ['id', 'author', 'comment', 'created_at']

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["id", "application", "file", "uploaded_at", "uploaded_by"]
        read_only_fields = ["id", "uploaded_at", "application", "uploaded_by"]

class ApplicationSerializer(serializers.ModelSerializer):
    patient = UserSerializer(read_only=True)
    history = ApplicationHistorySerializer(many=True, read_only=True)
    documents = DocumentSerializer(many=True, read_only=True)
    stage = StageSerializer(read_only=True)

    class Meta:
        model = Application
        fields = [
            "id", "application_id", "patient", "linked_patient",
            "clinic_name", "final_conclusion", "complaint", "diagnosis",
            "created_at", "updated_at", "stage", "documents", "history",
        ]