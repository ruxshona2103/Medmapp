from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


class UserAdmin(BaseUserAdmin):
    model = User
    list_display = ('first_name', 'last_name', 'phone', 'role', 'is_staff')
    search_fields = ('phone', 'first_name', 'last_name', 'email')


    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        ('Shaxsiy ma`lumotlar', {'fields': ('first_name', 'last_name', 'email', 'birth_date', 'gender')}),
        ('Ruxsatlar', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser')}),
        ('Tizim haqida', {'fields': ('last_login', 'date_joined')}),
    )


    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone', 'password1', 'password2', 'role', 'is_active')
        }),
    )
    ordering = ('-date_joined',)

admin.site.register(User, UserAdmin)

