from django.contrib import admin
from .models import Review, BlogPost, BlogCategory

# --------------------------------------------- REVIEWS --------------------------------------------------------
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("patient", "short_text", "is_approved", "created_at")
    list_filter = ("is_approved", "created_at")
    search_fields = ("patient__full_name", "text")

    def short_text(self, obj):
        return (obj.text[:70] + "...") if len(obj.text) > 70 else obj.text
    short_text.short_description = "Sharh matni"


# --------------------------------------------- BLOG -----------------------------------------------------------
@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name_uz", "name_ru", "name_en")
    search_fields = ("name_uz", "name_ru", "name_en")


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("title_uz", "category", "author", "created_at")
    list_filter = ("category", "created_at")
    search_fields = (
        "title_uz", "title_ru", "title_en",
        "description_uz", "description_ru", "description_en",
        "author",
    )
    readonly_fields = ("created_at",)
