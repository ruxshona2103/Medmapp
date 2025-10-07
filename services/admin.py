from django.contrib import admin
from .models import Hotel, Booking


@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "address", "stars", "price_per_night",)
    search_fields = ("name", "address")
    list_filter = ("stars",)

# lknqosgeiolqaolgijq
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "hotel", "start_date", "end_date", "guests", "created_at")
    search_fields = ("user__username", "hotel__name")
    list_filter = ("start_date", "end_date", "created_at")
