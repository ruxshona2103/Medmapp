from django.contrib import admin
from .models import Stage, Tag

@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "order", "color", "code_name")
    list_editable = ("order", "color", "code_name")
    search_fields = ("title", "code_name")
    ordering = ("order", "id")

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "color")
    search_fields = ("name",)

