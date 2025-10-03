# patients/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model

from applications.serializers import ApplicationSerializer
from .models import Patient, PatientProfile,  PatientDocument
from applications.models import Application

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "first_name", "role", "last_name", "full_name", "phone_number", "email"]
        ref_name = "PatientsUserSerializer"

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.phone_number or "Noma'lum"


class PatientDocumentSerializer(serializers.ModelSerializer):
    uploaded_by = UserSerializer(read_only=True)
    source_type_display = serializers.CharField(
        source="get_source_type_display", read_only=True
    )

    class Meta:
        model = PatientDocument
        fields = [
            "id",
            "file",
            "description",
            "uploaded_by",
            "uploaded_at",
            "source_type",
            "source_type_display",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if instance.file and request:
            data["file"] = request.build_absolute_uri(instance.file.url)
        return data

class PatientSerializer(serializers.ModelSerializer):
    stage_title = serializers.CharField(source="stage.title", read_only=True)
    tag_name = serializers.CharField(source="tag.name", read_only=True)
    tag_color = serializers.CharField(source="tag.color", read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = [
            "id",
            "full_name",
            "phone",
            "email",
            "region",
            "source",
            "stage_title",
            "tag_name",
            "tag_color",
            "created_at",
            "updated_at",
            "avatar_url",
        ]

    def get_avatar_url(self, obj):
        request = self.context.get("request")
        if obj.avatar and request:
            return request.build_absolute_uri(obj.avatar.url)
        return None

class PatientProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    applications = ApplicationSerializer(source="user.application_set", many=True, read_only=True)
    patient_records = PatientSerializer(many=True, read_only=True)
    full_name = serializers.CharField(max_length=150, write_only=True, required=False)
    email = serializers.EmailField(write_only=True, required=False)

    class Meta:
        model = PatientProfile
        fields = [
            "id",
            "user",
            "passport",
            "dob",
            "gender",
            "complaints",
            "previous_diagnosis",
            "patient_records",
            "applications",
            "full_name",
            "email",
        ]

    def update(self, instance, validated_data):
        full_name = validated_data.pop("full_name", None)
        email = validated_data.pop("email", None)
        user = instance.user

        if full_name:
            parts = full_name.split(" ", 1)
            user.first_name = parts[0]
            user.last_name = parts[1] if len(parts) > 1 else ""
            user.save(update_fields=["first_name", "last_name"])

            for patient in instance.patient_records.all():
                patient.full_name = full_name
                patient.save(update_fields=["full_name"])

        if email:
            user.email = email
            user.save(update_fields=["email"])
            for patient in instance.patient_records.all():
                patient.email = email
                patient.save(update_fields=["email"])

        return super().update(instance, validated_data)


class ApplicationStepSerializer(serializers.ModelSerializer):
    patient_data = UserSerializer(write_only=True, required=False)
    profile_data = PatientProfileSerializer(write_only=True, required=False)
    step = serializers.IntegerField(write_only=True, min_value=1, max_value=3)

    class Meta:
        model = Application
        fields = [
            "id",
            "application_id",
            "complaint",
            "diagnosis",
            "status",
            "patient",
            "patient_data",
            "profile_data",
            "step",
        ]

    def validate(self, data):
        step = data.get("step")
        if not step:
            raise serializers.ValidationError({"step": "Step is required."})

        patient_data = data.get("patient_data", {})
        profile_data = data.get("profile_data", {})

        if step == 1:
            if not all(k in patient_data for k in ["phone_number", "full_name"]):
                raise serializers.ValidationError({"patient_data": "Full name and phone number are required in step 1."})
        elif step == 2:
            if not all(k in profile_data for k in ["complaints", "previous_diagnosis"]):
                raise serializers.ValidationError({"profile_data": "Complaints and previous diagnosis are required in step 2."})
        elif step == 3:
            if "file" not in self.context.get("request").FILES:
                raise serializers.ValidationError({"file": "File upload is required in step 3."})

        return data

class Step1Serializer(serializers.Serializer):
    full_name = serializers.CharField(required=True)
    phone_number = serializers.CharField(required=True)
    passport = serializers.CharField(required=False)
    dob = serializers.DateField(required=False)
    gender = serializers.ChoiceField(choices=[("male","Male"),("female","Female")], required=False)
    email = serializers.EmailField(required=False)

class Step2Serializer(serializers.Serializer):
    complaints = serializers.CharField(required=True)
    previous_diagnosis = serializers.CharField(required=True)

class Step3Serializer(serializers.Serializer):
    file = serializers.FileField(required=True)

class ConsultationFormSerializer(serializers.Serializer):
    step = serializers.IntegerField(min_value=1, max_value=3)
    patient_data = Step1Serializer(required=False)
    profile_data = Step2Serializer(required=False)
    file = serializers.FileField(required=False)