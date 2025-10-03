# patients/admin.py
from django.contrib import admin
from .models import PatientProfile, Patient,  PatientDocument


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "full_name", "gender")
    search_fields = ("full_name", "user__phone_number")
    raw_id_fields = ("user",)



@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "phone",  "created_by", "created_at")
    list_filter = ( "created_by", "created_at")
    search_fields = ("full_name", "phone", "email")
    raw_id_fields = ("profile", "created_by")


@admin.register(PatientDocument)
class PatientDocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "uploaded_by", "file", "uploaded_at")
    search_fields = ("patient__full_name",)
    raw_id_fields = ("patient", "uploaded_by")