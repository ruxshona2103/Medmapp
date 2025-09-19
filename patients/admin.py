# patients/admin.py

from django.contrib import admin
from django.contrib.auth import get_user_model
from .models import Patient, PatientProfile, Stage, Tag, PatientHistory, PatientDocument

User = get_user_model()


# ==================================================
# 1. PatientHistory Inline — faqat Patient da ishlatiladi
# ==================================================
class PatientHistoryInline(admin.TabularInline):
    model = PatientHistory
    extra = 0
    readonly_fields = ['author', 'created_at']
    fields = ['author', 'comment', 'created_at']


# ==================================================
# 2. PatientDocument Inline — faqat Patient da ishlatiladi
# ==================================================
class PatientDocumentInline(admin.TabularInline):
    model = PatientDocument
    extra = 0
    readonly_fields = ['uploaded_by', 'uploaded_at']
    fields = ['file', 'description', 'uploaded_by', 'uploaded_at', 'source_type']


# ==================================================
# 3. Patient Admin — asosiy bemor jarayoni
# ==================================================
@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = [
        'full_name',
        'phone',
        'get_user_email',
        'stage',
        'tag',
        'created_by',
        'created_at'
    ]
    list_filter = ['stage', 'tag', 'created_by', 'created_at']
    search_fields = [
        'full_name',
        'phone',
        'profile__user__email',
        'profile__user__phone_number'
    ]
    inlines = [PatientHistoryInline, PatientDocumentInline]  # << Faqat Patient ga bog'langan
    raw_id_fields = ['profile', 'created_by']  # Tez ishlashi uchun

    def get_user_email(self, obj):
        if obj.profile and obj.profile.user:
            return obj.profile.user.email
        return "-"
    get_user_email.short_description = "Email (User)"
    get_user_email.admin_order_field = 'profile__user__email'


# ==================================================
# 4. PatientProfile Admin — bemorning shaxsiy ma'lumotlari
# ==================================================
@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = [
        'get_full_name',
        'get_phone',
        'passport',
        'dob',
        'gender'
    ]
    search_fields = [
        'user__first_name',
        'user__last_name',
        'user__phone_number',
        'passport'
    ]
    list_filter = ['gender']
    raw_id_fields = ['user']  # Tez ishlashi uchun

    def get_full_name(self, obj):
        if obj.user:
            return obj.user.get_full_name()
        return "-"
    get_full_name.short_description = "F.I.Sh"
    get_full_name.admin_order_field = 'user__first_name'

    def get_phone(self, obj):
        if obj.user:
            return obj.user.phone_number
        return "-"
    get_phone.short_description = "Telefon"
    get_phone.admin_order_field = 'user__phone_number'


# ==================================================
# 5. Stage Admin
# ==================================================
@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ['title', 'code_name', 'order', 'color']
    list_editable = ['order', 'color']
    ordering = ['order']


# ==================================================
# 6. Tag Admin
# ==================================================
@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'color']
    list_editable = ['color']


# ==================================================
# 7. PatientHistory Admin — alohida ham ko'rish
# ==================================================
@admin.register(PatientHistory)
class PatientHistoryAdmin(admin.ModelAdmin):
    list_display = ['patient', 'author', 'comment_preview', 'created_at']
    list_filter = ['author', 'created_at']
    search_fields = ['patient__full_name', 'author__first_name', 'comment']
    readonly_fields = ['created_at']

    def comment_preview(self, obj):
        return obj.comment[:50] + "..." if len(obj.comment) > 50 else obj.comment
    comment_preview.short_description = "Izoh (qisqacha)"


# ==================================================
# 8. PatientDocument Admin — alohida ham ko'rish
# ==================================================
@admin.register(PatientDocument)
class PatientDocumentAdmin(admin.ModelAdmin):
    list_display = [
        'patient',
        'get_uploaded_by',
        'description_preview',
        'uploaded_at',
        'source_type'
    ]
    list_filter = ['source_type', 'uploaded_by', 'uploaded_at']
    search_fields = ['patient__full_name', 'uploaded_by__first_name', 'description']
    readonly_fields = ['uploaded_at']

    def get_uploaded_by(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.get_full_name()
        return "-"
    get_uploaded_by.short_description = "Yuklagan"
    get_uploaded_by.admin_order_field = 'uploaded_by__first_name'

    def description_preview(self, obj):
        return obj.description[:50] + "..." if len(obj.description) > 50 else obj.description
    description_preview.short_description = "Tavsif"