from django.contrib import admin
from .models import PatientProfile


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "passport", "phone", "email", "gender", "created_at")
    search_fields = ("full_name", "passport", "phone", "email")
    list_filter = ("gender", "created_at")
    ordering = ("-created_at",)























