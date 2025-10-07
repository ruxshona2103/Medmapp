from django.contrib import admin
from .models import Patient, PatientHistory, PatientDocument, ChatMessage, Contract


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "phone_number", "stage", "tag", "is_archived", "created_at")
    list_filter = ("stage", "tag", "is_archived")
    search_fields = ("full_name", "phone_number", "email")


@admin.register(PatientHistory)
class PatientHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "author", "created_at")
    search_fields = ("patient__full_name", "author__username")


@admin.register(PatientDocument)
class PatientDocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "source_type", "uploaded_by", "uploaded_at")
    list_filter = ("source_type",)
    search_fields = ("patient__full_name",)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "sender", "timestamp")


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "status", "approved_at")
