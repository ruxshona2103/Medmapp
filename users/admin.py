from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from authentication.models import CustomUser

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('phone_number', 'full_name', 'role', 'is_active')
    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        ('Personal Info', {'fields': ('full_name',)}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser')}),
    )
    add_fieldsets = (
        (None, {'fields': ('phone_number', 'password1', 'password2', 'role')}),
    )
    search_fields = ('phone_number',)
    ordering = ('phone_number',)

admin.site.register(CustomUser, CustomUserAdmin)

