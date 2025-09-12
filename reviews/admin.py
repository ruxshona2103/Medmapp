from django.contrib import admin
from .models import Clinic, DoctorClinic, Review

@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ("name", "address", "phone")
    search_fields = ("name",)

@admin.register(DoctorClinic)
class DoctorClinicAdmin(admin.ModelAdmin):
    list_display = ("doctor", "clinic")
    list_filter = ("clinic",)
    search_fields = ("doctor__phone_number", "doctor__first_name", "doctor__last_name")

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "clinic", "doctor", "rating", "created_at")
    list_filter = ("rating", "clinic", "doctor")
    search_fields = ("text", "author__phone_number")
