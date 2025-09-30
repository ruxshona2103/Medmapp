# patients/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Patient, PatientProfile, Stage, Tag, PatientHistory, PatientDocument
from applications.models import Application

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "first_name","role",  "last_name", "full_name", "phone_number", "email"]
        ref_name = "PatientsUserSerializer"

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.phone_number or "Noma'lum"

class StageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stage
        fields = ["id", "title", "code_name", "order", "color"]

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "color"]

class PatientHistorySerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)

    class Meta:
        model = PatientHistory
        fields = ["id", "author", "comment", "created_at"]

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

class ApplicationSerializer(serializers.ModelSerializer):
    patient = UserSerializer(read_only=True)
    patient_data = UserSerializer(write_only=True, required=True)
    clinic_name = serializers.SerializerMethodField()
    phone = serializers.CharField(source="patient.phone_number", read_only=True, allow_null=True)
    email = serializers.CharField(source="patient.email", read_only=True, allow_null=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    patient_record = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = [
            "id",
            "application_id",
            "clinic_name",
            "complaint",
            "diagnosis",
            "status",
            "status_display",
            "created_at",
            "updated_at",
            "patient",
            "phone",
            "email",
            "patient_record",
            "patient_data",
        ]

    def get_clinic_name(self, obj):
        try:
            profile = obj.patient.patient_profile
            return profile.full_name or obj.patient.get_full_name() or "Medmapp Clinic"
        except (AttributeError, PatientProfile.DoesNotExist):
            return obj.patient.get_full_name() or "Medmapp Clinic"

    def get_patient_record(self, obj):
        try:
            patient = Patient.objects.get(
                profile__user=obj.patient,
                source=f"Application_{obj.id}"
            )
            return PatientSerializer(patient, context=self.context).data
        except Patient.DoesNotExist:
            return None

    def validate_patient_data(self, value):
        phone_number = value.get("phone_number")
        if not phone_number:
            raise serializers.ValidationError({"phone_number": "Telefon raqami majburiy."})
        return value

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