from rest_framework import serializers
from partners.models import PartnerResponseDocument
from .models import Stage, Tag
from patients.models import Patient


# =========================================================
# 🧾 Partner yuborgan fayllar
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
# 🧍 Stage ichidagi bemorlar (javob xatlari bilan)
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
        """Agar RESPONSES bosqichida bo‘lsa — partner fayllarini chiqaradi"""
        request = self.context.get("request")
        response_docs = PartnerResponseDocument.objects.filter(patient=obj).select_related("partner")
        return PartnerResponseDocumentMiniSerializer(response_docs, many=True, context={"request": request}).data


# =========================================================
# 🧩 Stage serializer
# =========================================================
class StageSerializer(serializers.ModelSerializer):
    patients = PatientInStageSerializer(many=True, read_only=True)  # 🆕 Shu joy muhim

    class Meta:
        model = Stage
        fields = ["id", "title", "order", "color", "code_name", "patients"]
        ref_name = "CoreStageSerializer"


# =========================================================
# 🏷️ Teglar
# =========================================================
class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "color"]
        ref_name = "CoreTagSerializer"
