from rest_framework import serializers
from .models import Review, BlogPost

# --------------------------------------------- REVIEWS --------------------------------------------------------
class ReviewSerializer(serializers.ModelSerializer):
    patient_full_name = serializers.CharField(source="patient.full_name", read_only=True)

    class Meta:
        model = Review
        fields = ["id", "patient_full_name", "text", "is_approved", "created_at"]


# --------------------------------------------- BLOG -----------------------------------------------------------
class BlogPostSerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()

    class Meta:
        model = BlogPost
        fields = [
            "id",
            "title_uz", "title_ru", "title_en",
            "description_uz", "description_ru", "description_en",
            "content_uz", "content_ru", "content_en",
            "author", "image", "category_name", "created_at",
        ]

    def get_category_name(self, obj):
        return obj.category.name_uz if obj.category else None
