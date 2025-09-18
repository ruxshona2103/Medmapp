# patients/serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Patient, PatientProfile, Stage, Tag, PatientHistory, PatientDocument

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Barcha ilovalarda ishlatiladigan umumiy foydalanuvchi serializer.
    ref_name farqligi uchun har bir ilovada alohida nom beriladi.
    """
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'role', 'phone_number']
        ref_name = "PatientsUserSerializer"  # <<<<<<< MUHIM: Swagger ziddiyati uchun


class StageSerializer(serializers.ModelSerializer):
    """
    Bosqich (Kanban ustuni)
    """
    class Meta:
        model = Stage
        fields = ['id', 'title', 'code_name', 'order', 'color']


class TagSerializer(serializers.ModelSerializer):
    """
    Teglar (VIP, Shoshilinch, Normal)
    """
    class Meta:
        model = Tag
        fields = ['id', 'name', 'color']


class PatientProfileSerializer(serializers.ModelSerializer):
    """
    Bemorning shaxsiy ma'lumotlari (passport, tug'ilgan sana, jinsi)
    """
    class Meta:
        model = PatientProfile
        fields = [
            'id', 'passport', 'dob', 'gender',
            'complaints', 'previous_diagnosis'
        ]


class PatientHistorySerializer(serializers.ModelSerializer):
    """
    Bemor tarixi (kim, qachon, nima o'zgartirildi)
    """
    author = UserSerializer(read_only=True)

    class Meta:
        model = PatientHistory
        fields = ['id', 'author', 'comment', 'created_at']


class PatientDocumentSerializer(serializers.ModelSerializer):
    """
    Hujjatlar (fayl, tavsif, kim yuklagan)
    """
    uploaded_by = UserSerializer(read_only=True)

    class Meta:
        model = PatientDocument
        fields = ['id', 'file', 'description', 'uploaded_by', 'uploaded_at', 'source_type']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        req = self.context.get('request')
        if instance.file and req:
            data['file'] = req.build_absolute_uri(instance.file.url)
        return data


class PatientSerializer(serializers.ModelSerializer):
    """
    Ro'yxat uchun qisqacha bemor ma'lumotlari
    """
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


class PatientDetailSerializer(serializers.ModelSerializer):
    """
    To'liq bemor ma'lumotlari (offcanvas)
    """
    profile = PatientProfileSerializer(read_only=True)
    history = PatientHistorySerializer(many=True, read_only=True)
    documents = PatientDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Patient
        fields = [
            'id', 'full_name', 'phone', 'email', 'source',
            'stage', 'tag', 'created_by',
            'profile', 'history', 'documents'
        ]


class PatientCreateSerializer(serializers.ModelSerializer):
    """
    Yangi bemor yaratishda profil ham kiritilishi mumkin
    """
    profile = PatientProfileSerializer(required=False)

    class Meta:
        model = Patient
        fields = [
            'full_name', 'phone', 'email', 'source',
            'stage', 'tag',
            'profile'
        ]

    def create(self, validated_data):
        profile_data = validated_data.pop('profile', None)
        patient = Patient.objects.create(**validated_data)
        if profile_data:
            PatientProfile.objects.create(patient=patient, **profile_data)
        return patient