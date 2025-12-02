from rest_framework import serializers
from django.conf import settings

# 1. Modellarni import qilish
from .models import Stage, Tag
from patients.models import Patient
# Agar PartnerResponseDocument partners appida bo'lsa:
from partners.models import PartnerResponseDocument

# =========================================================
# 1. BEMOR SERIALIZER (TAG UCHUN) - ENG TEPADA
# =========================================================
class PatientInTagSerializer(serializers.ModelSerializer):
    """Tag ichida ko'rinadigan qisqacha bemor ma'lumotlari"""
    class Meta:
        model = Patient
        fields = ["id", "full_name", "phone_number", "created_at"]

# =========================================================
# 2. PARTNER HUJJAT SERIALIZER
# =========================================================
class PartnerResponseDocumentMiniSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    partner_name = serializers.CharField(source="partner.name", read_only=True)

    class Meta:
        model = PartnerResponseDocument
        fields = ["id", "file_url", "description", "partner_name", "uploaded_at"]

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None

# =========================================================
# 3. STAGE UCHUN BEMOR SERIALIZER
# =========================================================
class PatientInStageSerializer(serializers.ModelSerializer):
    responses = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = [
            "id",
            "full_name",
            "phone_number",
            "complaints",
            "created_at",
            "responses",
        ]

    def get_responses(self, obj):
        request = self.context.get("request")
        # Bemorni javob xatlarini olish
        response_docs = PartnerResponseDocument.objects.filter(patient=obj).select_related("partner")
        return PartnerResponseDocumentMiniSerializer(response_docs, many=True, context={"request": request}).data

# =========================================================
# 4. STAGE SERIALIZER
# =========================================================
class StageSerializer(serializers.ModelSerializer):
    patients = PatientInStageSerializer(many=True, read_only=True)

    class Meta:
        model = Stage
        fields = ["id", "title", "order", "color", "code_name", "patients"]
        ref_name = "CoreStageSerializer"

# =========================================================
# 5. TAG SERIALIZER (ENG PASTDA BO'LISHI SHART)
# =========================================================
class TagSerializer(serializers.ModelSerializer):
    # ✅ Patient modelida related_name="patients" bo'lgani uchun avtomatik ishlaydi
    patients = PatientInTagSerializer(many=True, read_only=True)

    class Meta:
        model = Tag
        fields = ["id", "name", "code_name", "color", "patients"]
        ref_name = "CoreTagSerializer"