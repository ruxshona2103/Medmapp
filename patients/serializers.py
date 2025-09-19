from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Patient, PatientProfile, Stage, Tag, PatientHistory, PatientDocument

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'role', 'phone_number']
        ref_name = "PatientsUserSerializer"


class StageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stage
        fields = ['id', 'title', 'code_name', 'order', 'color']


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'color']


class PatientHistorySerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)

    class Meta:
        model = PatientHistory
        fields = ['id', 'author', 'comment', 'created_at']


class PatientDocumentSerializer(serializers.ModelSerializer):
    uploaded_by = UserSerializer(read_only=True)
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)

    class Meta:
        model = PatientDocument
        fields = ['id', 'file', 'description', 'uploaded_by', 'uploaded_at', 'source_type', 'source_type_display']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if instance.file and request:
            data['file'] = request.build_absolute_uri(instance.file.url)
        return data


class PatientSerializer(serializers.ModelSerializer):
    stage_title = serializers.CharField(source='stage.title', read_only=True)
    tag_name = serializers.CharField(source='tag.name', read_only=True)
    tag_color = serializers.CharField(source='tag.color', read_only=True)

    class Meta:
        model = Patient
        fields = [
            'id', 'full_name', 'phone', 'email', 'source',
            'stage_title', 'tag_name', 'tag_color',
            'created_at', 'updated_at'
        ]


class PatientProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    patient = PatientSerializer(source="patient_record", read_only=True)
    documents = PatientDocumentSerializer(many=True, read_only=True, source="patient_record.documents")
    history = PatientHistorySerializer(many=True, read_only=True, source="patient_record.history")

    class Meta:
        model = PatientProfile
        fields = [
            'id', 'user', 'passport', 'dob', 'gender',
            'complaints', 'previous_diagnosis',
            'patient', 'documents', 'history'
        ]
