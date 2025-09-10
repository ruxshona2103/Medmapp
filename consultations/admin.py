# consultations/admin.py
from django.contrib import admin
from .models import Conversation, Participant, Message, Attachment, ReadReceipt, DoctorSummary, Prescription

class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    fields = ("file", "original_name", "size", "mime_type", "uploaded_by", "uploaded_at")
    readonly_fields = ("size", "mime_type", "uploaded_by", "uploaded_at")

    # uploaded_by ni request.user ga qo'yish
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        formset.request = request
        return formset

    def save_new_instance(self, form, commit=True):
        instance = super().save_new_instance(form, commit=False)
        if not getattr(instance, "uploaded_by_id", None):
            instance.uploaded_by = self.formset.request.user
        if commit:
            instance.save()
        return instance

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "type", "created_at", "is_deleted")
    list_filter = ("type", "is_deleted")
    search_fields = ("content", "conversation__title", "sender__first_name", "sender__last_name")
    inlines = [AttachmentInline]  # Attachment’larni xabar ichida qo‘shasiz

@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("id", "message", "original_name", "mime_type", "size", "uploaded_by", "uploaded_at")
    readonly_fields = ("size", "mime_type", "uploaded_at")

    def save_model(self, request, obj, form, change):
        if not obj.uploaded_by_id:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)
