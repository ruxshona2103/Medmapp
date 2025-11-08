from rest_framework import serializers
from .models import Review, BlogPost, BlogCategory


# === Helper function ===
def tr(obj, base: str):
    """Return dict with all languages: {'uz':..., 'ru':..., 'en':...}"""
    return {
        "uz": getattr(obj, f"{base}_uz", None),
        "ru": getattr(obj, f"{base}_ru", None),
        "en": getattr(obj, f"{base}_en", None),
    }


# --------------------------------------------- REVIEWS --------------------------------------------------------
class ReviewSerializer(serializers.ModelSerializer):
    patient_full_name = serializers.CharField(source="patient.full_name", read_only=True)

    class Meta:
        model = Review
        fields = ["id", "patient_full_name", "text", "is_approved", "created_at"]


# --------------------------------------------- BLOG CATEGORY --------------------------------------------------
class BlogCategorySerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = BlogCategory
        fields = ["id", "name"]

    def get_name(self, obj):
        return tr(obj, "name")


# --------------------------------------------- BLOG -----------------------------------------------------------
class BlogPostSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()
    category = BlogCategorySerializer(read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = BlogPost
        fields = [
            "id",
            "title",
            "description",
            "content",
            "author",
            "image_url",
            "category",
            "created_at",
        ]

    def get_title(self, obj):
        return tr(obj, "title")

    def get_description(self, obj):
        return tr(obj, "description")

    def get_content(self, obj):
        return tr(obj, "content")

    def get_image_url(self, obj):
        try:
            if obj.image:
                request = self.context.get("request")
                if request:
                    return request.build_absolute_uri(obj.image.url)
                return obj.image.url
        except:
            pass
        return None
