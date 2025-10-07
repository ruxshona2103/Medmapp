from rest_framework import serializers
from .models import Stage, Tag

class StageSerializer(serializers.ModelSerializer):
    """Bosqichlar uchun serializer (TZ 3.3)"""
    class Meta:
        model = Stage
        fields = ["id", "title", "order", "color", "code_name"]
        ref_name = "CoreStageSerializer"  # patients bilan kolliziya bo‘lmasin

class TagSerializer(serializers.ModelSerializer):
    """Teglar uchun serializer (TZ 3.2)"""
    class Meta:
        model = Tag
        fields = ["id", "name", "color"]
        ref_name = "CoreTagSerializer"
