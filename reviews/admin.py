from django.contrib import admin
from .models import Clinic, DoctorClinic, Review

from django.contrib import admin
from .models import Clinic, DoctorClinic, Review

from django.contrib import admin
from .models import Clinic

@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "address",
        "phone",
        "specialties",
        "rating",  # Rating added
        "workingHours",  # Working hours added
        "image"  # Image added
    )

    search_fields = (
        "name",
        "address",
        "phone",
        "specialties"
    )

    # Admin form layout
    fieldsets = (
        (None, {
            'fields': (
                'name',
                'address',
                'phone',
                'description',
                'specialties',
                'rating',  # Rating field added
                'workingHours',  # Working hours field added
                'image'  # Image field added
            )
        }),
    )

@admin.register(DoctorClinic)
class DoctorClinicAdmin(admin.ModelAdmin):
    list_display = ("doctor", "clinic")
    list_filter = ("clinic",)
    search_fields = ("doctor__phone_number", "doctor__first_name", "doctor__last_name")

    # DoctorClinic admin formasi (Create yoki Update uchun)
    fieldsets = (
        (None, {
            'fields': ('doctor', 'clinic')
        }),
    )


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    # Review ro‘yxatini ko‘rsatish uchun kerakli maydonlar
    list_display = ("id", "author", "clinic", "doctor", "rating", "created_at", "text", "video")
    list_filter = ("rating", "clinic", "doctor")
    search_fields = ("text", "author__phone_number", "author__first_name", "author__last_name")

    # Review admin formasi (Create yoki Update uchun)
    fieldsets = (
        (None, {
            'fields': ('author', 'clinic', 'doctor', 'rating', 'text', 'video')
        }),
    )
