from django.contrib import admin
from .models import PatientProfile, Patient, Stage, Tag, PatientHistory, PatientDocument


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "full_name", "gender")
    search_fields = ("full_name", "user__phone_number")
    raw_id_fields = ("user",)


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "code_name", "order")
    list_editable = ("order",)
    search_fields = ("title", "code_name")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "phone", "stage", "tag", "created_by", "created_at")
    list_filter = ("stage", "tag", "created_by", "created_at")
    search_fields = ("full_name", "phone", "email")
    raw_id_fields = ("profile", "created_by")


@admin.register(PatientHistory)
class PatientHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "author", "comment", "created_at")
    search_fields = ("comment",)
    raw_id_fields = ("patient", "author")


@admin.register(PatientDocument)
class PatientDocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "uploaded_by", "file", "uploaded_at")
    search_fields = ("patient__full_name",)
    raw_id_fields = ("patient", "uploaded_by")
