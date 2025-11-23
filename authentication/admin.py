from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, MedicalFile, OTP, OperatorProfile

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = (
        'phone_number', 'first_name', 'last_name',
        'district', 'role', 'is_active', 'is_staff', 'date_joined'
    )
    list_filter = ('role', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('phone_number', 'first_name', 'last_name')
    readonly_fields = ('date_joined', 'last_login')  # bu qator qo‘shildi
    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'district')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'password1', 'password2', 'role', 'is_active', 'is_staff', 'is_superuser')}
        ),
    )
    ordering = ('-date_joined',)

@admin.register(MedicalFile)
class MedicalFileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'file', 'uploaded_at')
    search_fields = ('user__phone_number',)
    list_filter = ('uploaded_at',)

@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'code', 'created_at', 'expires_at')
    search_fields = ('user__phone_number', 'code')
    list_filter = ('created_at', 'expires_at')


# CustomUser ham admin panelga qo'shiladi
admin.site.register(CustomUser, CustomUserAdmin)


@admin.register(OperatorProfile)
class OperatorProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'full_name', 'employee_id', 'department', 'phone', 'is_active', 'created_at')
    list_filter = ('is_active', 'department', 'created_at')
    search_fields = ('full_name', 'employee_id', 'phone', 'user__phone_number')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('user',)
