from django.contrib import admin
from django import forms
from .models import Review, BlogPost, BlogCategory


# ===============================================
# 🔹 Custom Review Form (faqat superadmin uchun 3 tilda)
# ===============================================
class ReviewAdminForm(forms.ModelForm):
    text_uz = forms.CharField(label="Sharh (UZ)", widget=forms.Textarea, required=False)
    text_ru = forms.CharField(label="Sharh (RU)", widget=forms.Textarea, required=False)
    text_en = forms.CharField(label="Sharh (EN)", widget=forms.Textarea, required=False)

    class Meta:
        model = Review
        fields = "__all__"

    def save(self, commit=True):
        # 3 tildagi matnlarni yagona text maydoniga birlashtiramiz
        text_combined = f"UZ: {self.cleaned_data.get('text_uz', '')}\n\nRU: {self.cleaned_data.get('text_ru', '')}\n\nEN: {self.cleaned_data.get('text_en', '')}"
        self.instance.text = text_combined
        return super().save(commit=commit)


# ===============================================
# 🔹 REVIEWS ADMIN
# ===============================================
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    form = ReviewAdminForm
    list_display = ("patient", "short_text", "is_approved", "created_at")
    list_filter = ("is_approved", "created_at")
    search_fields = ("patient__full_name", "text")
    readonly_fields = ("created_at",)

    def short_text(self, obj):
        return (obj.text[:70] + "...") if obj.text else "-"
    short_text.short_description = "Sharh matni"

    def get_form(self, request, obj=None, **kwargs):
        """Superuserlar uchun 3 tilli form, boshqalarga oddiy"""
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser:
            # oddiy adminlardan 3 tildagi maydonlarni yashiramiz
            for field in ["text_uz", "text_ru", "text_en"]:
                if field in form.base_fields:
                    form.base_fields.pop(field)
        return form


# ===============================================
# 🔹 BLOG CATEGORY ADMIN
# ===============================================
@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name_uz", "name_ru", "name_en")
    search_fields = ("name_uz", "name_ru", "name_en")


# ===============================================
# 🔹 BLOG POST ADMIN
# ===============================================
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
