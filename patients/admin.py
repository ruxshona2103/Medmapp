from django.contrib import admin
from .models import PatientProfile, Application, Document, Service, OrderedService, ServiceStatusHistory

@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ("fullName", "user", "phone", "email")
    search_fields = ("fullName", "passport", "phone", "email", "user__username")

class DocumentInline(admin.TabularInline):
    model = Document
    extra = 0

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("patient__username", "patient__email", "complaint")
    inlines = [DocumentInline]

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("service_id", "name", "price", "price_description")
    search_fields = ("service_id", "name")

class OrderedServiceInline(admin.TabularInline):
    model = OrderedService
    extra = 0

@admin.register(OrderedService)
class OrderedServiceAdmin(admin.ModelAdmin):
    list_display = ("id", "service", "application", 'order_date', 'current_status_index')

@admin.register(ServiceStatusHistory)
class ServiceStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('ordered_service', 'status_text', 'date')
    list_filter = ('date',)























