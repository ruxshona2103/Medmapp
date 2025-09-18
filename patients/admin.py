# patients/admin.py

from django.contrib import admin
from .models import Patient, PatientProfile, Stage, Tag, PatientHistory, PatientDocument

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'phone', 'stage', 'tag', 'created_by', 'created_at']
    list_filter = ['stage', 'tag', 'created_by']
    search_fields = ['full_name', 'phone']

@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ['patient', 'passport', 'dob', 'gender']
    search_fields = ['patient__full_name', 'passport']

@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ['title', 'code_name', 'order']

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'color']
