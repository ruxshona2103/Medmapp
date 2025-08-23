from rest_framework import serializers
from .models import Application, Document


class ApplicationSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)

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
            "updated_at"
        ]
        read_only_fields = ["application_id", "status", "created_at", "updated_at"]

    def create(self, validated_data):
        request = self.context.get("request")
        validated_data["patient"] = request.user
        return super().create(validated_data)


class DocumentSerializer(serializers.ModelSerializer):
    application = serializers.PrimaryKeyRelatedField(queryset=Application.objects.all())
    class Meta:
        model = Document
        fields = ["id", "application", "file", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]


