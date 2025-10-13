from rest_framework import serializers
from .models import Stage, Tag
from patients.models import Patient


class PatientShortSerializer(serializers.ModelSerializer):
    """Stage ichidagi bemorlar uchun qisqa info (ID, ism, telefon, holat)."""
    class Meta:
        model = Patient
        fields = ["id", "full_name", "phone_number", "complaints", "created_at"]


class StageSerializer(serializers.ModelSerializer):
    """
    Bosqichlar uchun serializer (TZ 3.3)
    - Agar operator so‘rasa, stage ichidagi bemorlar ham qaytariladi.
    """
    patients = PatientShortSerializer(many=True, read_only=True)

    class Meta:
        model = Stage
        fields = ["id", "title", "order", "color", "code_name", "patients"]
        ref_name = "CoreStageSerializer"  # Swagger nomi unikal bo‘lsin


class TagSerializer(serializers.ModelSerializer):
    """Teglar uchun serializer (TZ 3.2)."""
    class Meta:
        model = Tag
        fields = ["id", "name", "color"]
        ref_name = "CoreTagSerializer"
