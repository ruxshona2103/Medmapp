from django.contrib.auth import get_user_model
from django.db.models import Avg, Count
from rest_framework import serializers
from .models import Clinic, DoctorClinic, Review

User = get_user_model()


class ClinicSerializer(serializers.ModelSerializer):
    rating = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    rating_distribution = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()  # Rasm URL preview uchun qo‘shildi

    class Meta:
        model = Clinic
        fields = [
            "id", "name", "address", "phone", "specialties", "rating", "workingHours", "image",
            "rating_count", "rating_distribution", "description"
        ]

    def get_image(self, obj):
        """Swagger preview uchun to‘liq media URL qaytaradi"""
        request = self.context.get("request")
        if hasattr(obj, "image") and obj.image:
            try:
                return request.build_absolute_uri(obj.image.url)
            except Exception:
                return None
        return None

    def get_rating(self, obj):
        return round(obj.reviews.aggregate(a=Avg("rating"))["a"] or 0, 1)

    def get_rating_count(self, obj):
        return obj.reviews.count()

    def get_rating_distribution(self, obj):
        dist = {i: 0 for i in range(1, 6)}
        for row in obj.reviews.values("rating").annotate(c=Count("id")):
            dist[row["rating"]] = row["c"]
        return dist

class ReviewSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ["id", "author", "author_name", "clinic", "doctor", "rating", "text", "video", "created_at"]
        read_only_fields = ["author", "author_name", "created_at"]

    def get_author_name(self, obj):
        name = f"{obj.author.first_name or ''} {obj.author.last_name or ''}".strip()
        return name or getattr(obj.author, "phone_number", "")

    def validate(self, attrs):
        if not (attrs.get("clinic") or attrs.get("doctor")):
            raise serializers.ValidationError("Clinic yoki Doctor majburiy.")
        return attrs

    def create(self, validated_data):
        validated_data["author"] = self.context["request"].user
        return super().create(validated_data)

class DoctorSerializer(serializers.ModelSerializer):
    clinic = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "phone_number", "clinic"]

    def get_clinic(self, obj):
        dc = getattr(obj, "doctor_clinic", None)
        if not dc:
            return None
        return ClinicSerializer(dc.clinic, context=self.context).data