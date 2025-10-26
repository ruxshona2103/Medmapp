# partners/admin.py
# ===============================================================
# HAMKOR PANEL - ADMIN
# ===============================================================

from django.contrib import admin
from .models import Partner, PartnerResponseDocument


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    """Partner admin"""
    list_display = [
        'name',
        'code',
        'specialization',
        'contact_person',
        'phone',
        'is_active',
        'total_patients',
        'active_patients',
        'created_at',
    ]
    list_filter = ['is_active', 'specialization', 'created_at']
    search_fields = ['name', 'code', 'contact_person', 'phone']
    readonly_fields = ['created_at', 'updated_at', 'total_patients', 'active_patients']

    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('user', 'name', 'code', 'specialization')
        }),
        ('Aloqa', {
            'fields': ('contact_person', 'phone', 'email')
        }),
        ('Telegram', {
            'fields': ('telegram_chat_id',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Statistika', {
            'fields': ('total_patients', 'active_patients'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PartnerResponseDocument)
class PartnerResponseDocumentAdmin(admin.ModelAdmin):
    """Partner response document admin"""
    list_display = [
        'id',
        'partner',
        'patient',
        'title',
        'document_type',
        'file_name',
        'uploaded_at',
    ]
    list_filter = ['document_type', 'uploaded_at', 'partner']
    search_fields = ['patient__full_name', 'partner__name', 'title', 'file_name']
    readonly_fields = ['uploaded_at', 'file_name']

    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('patient', 'partner', 'file', 'file_name')
        }),
        ('Hujjat ma\'lumotlari', {
            'fields': ('title', 'description', 'document_type')
        }),
        ('Timestamp', {
            'fields': ('uploaded_at',)
        }),
    )
