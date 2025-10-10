from django.contrib import admin
from .models import Application, ApplicationHistory, Document

class DocumentInline(admin.TabularInline):
    model = Document
    extra = 0
    readonly_fields = ("uploaded_by", "uploaded_at")

class ApplicationHistoryInline(admin.TabularInline):
    model = ApplicationHistory
    extra = 0
    readonly_fields = ("author", "created_at")

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("application_id", "patient", "stage", "status",  "created_at", "is_archived")
    list_filter  = ("status", "stage", "is_archived", "created_at")
    search_fields = ("application_id", "patient__full_name", "patient__phone_number", "clinic_name")
    readonly_fields = ("application_id", "created_at", "updated_at", "archived_at")
    inlines = [DocumentInline, ApplicationHistoryInline]

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "application", "description", "uploaded_by", "uploaded_at")
    search_fields = ("application__application_id", "description")

@admin.register(ApplicationHistory)
class ApplicationHistoryAdmin(admin.ModelAdmin):
    list_display = ("application", "author", "comment", "created_at")
    search_fields = ("application__application_id", "comment")
    readonly_fields = ("created_at",)
