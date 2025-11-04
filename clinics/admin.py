from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Country, City, Accreditation, Specialty, Clinic, ClinicSpecialty,
    Doctor, TreatmentPrice, ClinicInfrastructure, ClinicImage, NearbyStay
)

# === Country ===
@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "title_uz")
    search_fields = ("code", "title_uz", "title_ru", "title_en")


# === City ===
@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("id", "title_uz", "country")
    list_filter = ("country",)
    search_fields = ("title_uz", "title_ru", "title_en")


# === Accreditation ===
@admin.register(Accreditation)
class AccreditationAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


# === Specialty ===
@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ("id", "title_uz", "is_active")
    list_filter = ("is_active",)
    search_fields = ("title_uz", "title_ru", "title_en")


# === Inline classes ===
class ClinicSpecialtyInline(admin.TabularInline):
    model = ClinicSpecialty
    extra = 1


class DoctorInline(admin.TabularInline):
    model = Doctor
    extra = 0
    fields = ("full_name", "specialty", "is_top", "order")


class PriceInline(admin.TabularInline):
    model = TreatmentPrice
    extra = 0
    fields = ("specialty", "procedure_uz", "price_usd", "order", "is_active")


class InfraInline(admin.TabularInline):
    model = ClinicInfrastructure
    extra = 0


class GalleryInline(admin.TabularInline):
    model = ClinicImage
    extra = 0
    readonly_fields = ("preview",)

    def preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 80px; height: 60px; object-fit: cover;" />', obj.image.url)
        return "—"
    preview.short_description = "Preview"


class NearbyInline(admin.TabularInline):
    model = NearbyStay
    extra = 0


# === Clinic ===
@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ("id", "title_uz", "country", "city", "rating", "is_active")
    list_filter = ("country", "city", "is_active", "accreditations")
    search_fields = ("title_uz", "title_ru", "title_en", "address_uz", "address_ru", "address_en")
    prepopulated_fields = {"slug": ("title_uz",)}
    filter_horizontal = ("accreditations",)
    inlines = [ClinicSpecialtyInline, DoctorInline, PriceInline, InfraInline, GalleryInline, NearbyInline]


# === Doctor ===
@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ("full_name", "clinic", "specialty", "is_top", "order")
    list_filter = ("clinic", "specialty", "is_top")
    search_fields = ("full_name",)


# === Treatment Price ===
@admin.register(TreatmentPrice)
class TreatmentPriceAdmin(admin.ModelAdmin):
    list_display = ("clinic", "specialty", "procedure_uz", "price_usd", "order", "is_active")
    list_filter = ("clinic", "specialty", "is_active")
    search_fields = ("procedure_uz", "procedure_ru", "procedure_en")


# === Clinic Infrastructure ===
@admin.register(ClinicInfrastructure)
class ClinicInfraAdmin(admin.ModelAdmin):
    list_display = ("clinic", "text_uz", "order")
    list_filter = ("clinic",)


# === Clinic Gallery (alohida bo‘lim sifatida) ===
@admin.register(ClinicImage)
class ClinicImageAdmin(admin.ModelAdmin):
    list_display = ("preview", "clinic", "title_uz", "order")
    list_filter = ("clinic",)
    readonly_fields = ("preview",)

    def preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 100px; height: 80px; object-fit: cover;" />', obj.image.url)
        return "—"
    preview.short_description = "Rasm"


# === Nearby Stay ===
@admin.register(NearbyStay)
class NearbyAdmin(admin.ModelAdmin):
    list_display = ("clinic", "title_uz", "rating")
    list_filter = ("clinic",)
