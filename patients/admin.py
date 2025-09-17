# patients/admin.py
from django.contrib import admin
from .models import PatientProfile, Stage, Tag, PatientDocument, PatientHistory, ChatMessage, Contract

@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "code_name", "order", "color")
    ordering = ("order", "id")
    search_fields = ("title", "code_name")

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "color")
    search_fields = ("name",)

@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "phone", "email", "user", "created_by", "stage", "tag", "created_at")
    list_filter = ("stage", "tag", "created_at")
    search_fields = ("full_name", "phone", "email", "passport")
    readonly_fields = ("created_at", "updated_at")
    fields = ("user", "created_by", "full_name", "passport", "dob", "gender", "phone", "email", "stage", "tag", "avatar", "created_at", "updated_at")

@admin.register(PatientDocument)
class PatientDocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "patient_profile", "uploaded_by", "source_type", "uploaded_at")
    list_filter  = ("source_type", "uploaded_at")
    search_fields = ("patient_profile__full_name",)

@admin.register(PatientHistory)
class PatientHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "patient_profile", "author", "comment", "created_at")
    list_filter = ("created_at",)
    search_fields = ("patient_profile__full_name", "comment")

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "patient_profile", "sender", "timestamp")
    list_filter = ("timestamp",)
    search_fields = ("patient_profile__full_name",)

@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ("id", "patient_profile", "status", "approved_by", "approved_at")
    list_filter  = ("status",)
    search_fields = ("patient_profile__full_name",)
