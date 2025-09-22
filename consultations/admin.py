# consultations/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import Conversation, Participant, Message, Attachment, MessageReadStatus


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    fields = ("file", "original_name", "file_type", "size", "mime_type", "uploaded_by")
    readonly_fields = ("size", "mime_type", "uploaded_by", "uploaded_at")

    def has_add_permission(self, request, obj=None):
        return True

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conversation_link",
        "sender_link",
        "type",
        "content_preview",
        "created_at",
        "is_read_display",
    )
    list_filter = ("type", "created_at", "is_deleted", "is_read_by_recipient")
    search_fields = (
        "content",
        "conversation__title",
        "sender__first_name",
        "sender__last_name",
    )
    list_per_page = 50
    date_hierarchy = "created_at"
    inlines = [AttachmentInline]

    def conversation_link(self, obj):
        url = f"/admin/consultations/conversation/{obj.conversation_id}/change/"
        return format_html('<a href="{}">{}</a>', url, obj.conversation)

    conversation_link.short_description = "Suhbat"

    def sender_link(self, obj):
        url = f"/admin/auth/user/{obj.sender_id}/change/"
        return format_html('<a href="{}">{}</a>', url, obj.sender.get_full_name())

    sender_link.short_description = "Yuborgan"

    def content_preview(self, obj):
        if obj.is_deleted:
            return "[O'chirilgan]"
        if obj.content:
            preview = obj.content[:50]
            return preview + "..." if len(obj.content) > 50 else preview
        elif obj.attachments.exists():
            return f"Fayl: {obj.attachments.first().original_name[:30]}"
        return ""

    content_preview.short_description = "Kontent"

    def is_read_display(self, obj):
        if obj.is_read_by_recipient:
            return mark_safe('<span style="color: green;">✓ O\'qilgan</span>')
        return mark_safe('<span style="color: orange;">○ O\'qilmagan</span>')

    is_read_display.short_description = "Holati"


class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 0
    fields = ("user", "role", "joined_at", "is_muted", "last_seen_at")
    readonly_fields = ("joined_at", "last_seen_at")


class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "patient_link",
        "operator_link",
        "created_by_link",
        "last_message_at",
        "message_count",
        "is_active",
    )
    list_filter = ("is_active", "last_message_at")  # created_at olib tashlandi
    search_fields = (
        "title",
        "patient__first_name",
        "patient__last_name",
        "operator__first_name",
        "operator__last_name",
    )
    list_per_page = 25
    date_hierarchy = "last_message_at"  # created_at o‘rniga
    inlines = [ParticipantInline]


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "message_link",
        "original_name",
        "file_type",
        "formatted_size",
        "uploaded_by_link",
        "uploaded_at",
    )
    list_filter = ("file_type", "mime_type", "uploaded_at")
    search_fields = ("original_name", "message__content", "uploaded_by__first_name")
    readonly_fields = ("size", "mime_type", "uploaded_at")
    date_hierarchy = "uploaded_at"

    def message_link(self, obj):
        url = f"/admin/consultations/message/{obj.message_id}/change/"
        return format_html('<a href="{}">Msg#{}</a>', url, obj.message_id)

    message_link.short_description = "Xabar"

    def uploaded_by_link(self, obj):
        url = f"/admin/auth/user/{obj.uploaded_by_id}/change/"
        return format_html('<a href="{}">{}</a>', url, obj.uploaded_by.get_full_name())

    uploaded_by_link.short_description = "Yuklagan"

    def formatted_size(self, obj):
        return obj.formatted_size

    formatted_size.short_description = "Hajm"
    formatted_size.admin_order_field = "size"


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = (
        "conversation",
        "user_link",
        "role",
        "joined_at",
        "is_muted",
        "last_seen",
    )
    list_filter = ("role", "is_muted", "joined_at")
    search_fields = ("user__first_name", "user__last_name", "conversation__title")
    list_per_page = 50

    def user_link(self, obj):
        url = f"/admin/auth/user/{obj.user_id}/change/"
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name())

    user_link.short_description = "Foydalanuvchi"

    def last_seen(self, obj):
        if obj.last_seen_at:
            return obj.last_seen_at.strftime("%d.%m.%Y %H:%M")
        return "Hech qachon"

    last_seen.short_description = "Oxirgi ko'rish"
    last_seen.admin_order_field = "last_seen_at"


@admin.register(MessageReadStatus)
class MessageReadStatusAdmin(admin.ModelAdmin):
    list_display = ("message_id", "user_link", "read_at", "is_read")
    list_filter = ("is_read", "read_at")
    search_fields = ("user__first_name", "user__last_name")
    date_hierarchy = "read_at"
    list_per_page = 100

    def user_link(self, obj):
        url = f"/admin/auth/user/{obj.user_id}/change/"
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name())

    user_link.short_description = "Foydalanuvchi"
