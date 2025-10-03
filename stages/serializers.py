# patients/serializers.py
from rest_framework import serializers
from .models import Stage

class StageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stage
        fields = "__all__"
        ref_name = "PatientStageSerializer"   # 🔥 unique nom berildi
