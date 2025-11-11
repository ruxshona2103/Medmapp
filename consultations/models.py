"""
Consultations app modellari.
Bu faylda suhbat, xabarlar, ishtirokchilar va fayllar modellari aniqlanadi.
"""

from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import models
from django.utils import timezone
import os
import mimetypes

# 🔗 Bemor profili
from patients.models import Patient

User = get_user_model()


# ---------- Asosiy suhbat ----------
class Conversation(models.Model):
    """
    Suhbat model. Bemor va operator o'rtasidagi suhbatni ifodalaydi.
    """
    title = models.CharField(max_length=255, blank=True)

    # Kim yaratgan (odatda operator)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_conversations",
    )

    # Patient model bilan bog'lanish
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.PROTECT,
        related_name="conversations",
    )

    # Operator – User bo'lib qoladi
    operator = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="operator_conversations",
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)
    last_message_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["patient", "operator"],
                name="uniq_patient_operator_conversation",
                condition=models.Q(is_active=True),
            )
        ]
        ordering = ["-last_message_at", "-id"]
        indexes = [
            models.Index(fields=["patient", "is_active"]),
            models.Index(fields=["operator", "is_active"]),
            models.Index(fields=["last_message_at"]),
        ]

    def __str__(self) -> str:
        patient_name = getattr(self.patient, 'get_full_name', lambda: str(self.patient))()
        if self.operator:
            return self.title or f"Operator suhbat #{self.pk} - {patient_name}"
        return self.title or f"Suhbat #{self.pk} - {patient_name}"

    def save(self, *args, **kwargs):
        if not self.operator and self.created_by:
            self.operator = self.created_by
        super().save(*args, **kwargs)

    @property
    def patient_user(self):
        """Patient modelidagi user ni qaytaradi"""
        return getattr(self.patient, "user", None)


# ---------- Ishtirokchilar ----------
class Participant(models.Model):
    """
    Suhbat ishtirokchisi model. Suhbatdagi foydalanuvchi rolini ifodalaydi.
    """
    ROLE_CHOICES = (
        ("patient", "Patient"),
        ("operator", "Operator"),
    )

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="participants"
    )

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="chat_participations"
    )

    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    joined_at = models.DateTimeField(default=timezone.now)
    is_muted = models.BooleanField(default=False)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("conversation", "user")]
        indexes = [
            models.Index(fields=["conversation", "role"]),
            models.Index(fields=["user", "is_muted"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} in {self.conversation} as {self.role}"


# ---------- Xabarlar ----------
class Message(models.Model):
    """
    Xabar model. Suhbatdagi xabarlarni ifodalaydi.
    """
    TYPE_CHOICES = (("text", "Text"), ("file", "File"), ("system", "System"))

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="sent_messages"
    )
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="text")
    content = models.TextField(blank=True, null=True)
    reply_to = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="replies"
    )
    created_at = models.DateTimeField(default=timezone.now)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    is_read_by_recipient = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["conversation", "id"]),
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["sender", "created_at"]),
            models.Index(fields=["reply_to"]),
        ]

    def __str__(self) -> str:
        return f"Msg#{self.pk} in Conv#{self.conversation_id}"

    def soft_delete(self):
        self.is_deleted = True
        self.content = "[O'chirilgan xabar]"
        self.save(update_fields=["is_deleted", "content"])

    def mark_as_read(self, user):
        if user != self.sender:
            self.is_read_by_recipient = True
            self.save(update_fields=["is_read_by_recipient"])


# ---------- Fayllar ----------
def chat_upload_path(instance: "Attachment", filename: str) -> str:
    """
    Fayl yuklash yo'lini aniqlash.
    """
    timestamp = timezone.now()
    safe_filename = "".join(
        c for c in os.path.basename(filename) if c.isalnum() or c in "._-"
    )
    return f"chat_attachments/{timestamp:%Y/%m/%d}/{instance.message_id}_{safe_filename}"


class Attachment(models.Model):
    """
    Xabarga biriktirilgan fayl model.
    """
    FILE_TYPE_CHOICES = (
        ("image", "Image"),
        ("video", "Video"),
        ("document", "Document"),
        ("other", "Other"),
    )

    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(upload_to=chat_upload_path)
    file_type = models.CharField(
        max_length=20, choices=FILE_TYPE_CHOICES, default="other"
    )
    mime_type = models.CharField(max_length=100, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    original_name = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="chat_files"
    )
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["message", "uploaded_at"]),
            models.Index(fields=["uploaded_by"]),
        ]

    def save(self, *args, **kwargs):
        if self.file:
            self.original_name = (
                os.path.basename(self.file.name) if hasattr(self.file, "name") else ""
            )
            if hasattr(self.file, "size"):
                self.size = self.file.size

            # MIME aniqlash
            if hasattr(self.file, "content_type") and self.file.content_type:
                self.mime_type = self.file.content_type
            elif self.original_name:
                guessed, _ = mimetypes.guess_type(self.original_name)
                self.mime_type = guessed or "application/octet-stream"
            else:
                self.mime_type = self.mime_type or "application/octet-stream"

            # Fayl turini MIME'dan kelib chiqib belgilash
            if self.mime_type.startswith("image/"):
                self.file_type = "image"
            elif self.mime_type.startswith("video/"):
                self.file_type = "video"
            elif self.mime_type.startswith(
                ("application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument")
            ):
                self.file_type = "document"
            else:
                self.file_type = "other"

        super().save(*args, **kwargs)

    def get_file_url(self):
        return self.file.url if self.file else None

    @property
    def formatted_size(self):
        size = self.size
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def __str__(self):
        return f"{self.original_name} - {self.formatted_size}"


# ---------- O'qilgan xabarlar tracking'i ----------
class MessageReadStatus(models.Model):
    """
    Xabar o'qilgan holatini kuzatish model.
    """
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="read_statuses"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="message_read_statuses"
    )
    read_at = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=True)

    class Meta:
        unique_together = [("message", "user")]
        indexes = [
            models.Index(fields=["message", "user"]),
            models.Index(fields=["user", "read_at"]),
        ]

    def __str__(self):
        return f"Msg#{self.message.id} read by {self.user} at {self.read_at}"


# ---------- Suhbat statistikasi ----------
class ConversationStats(models.Model):
    """
    Suhbat statistikasi model.
    """
    conversation = models.OneToOneField(
        Conversation, on_delete=models.CASCADE, related_name="stats"
    )
    total_messages = models.PositiveIntegerField(default=0)
    total_files = models.PositiveIntegerField(default=0)
    first_message_at = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_activity_at"]

    def __str__(self):
        return f"Stats for {self.conversation}"


# ---------- Retsept ----------
class Prescription(models.Model):
    """
    Retsept model.
    """
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="prescriptions"
    )
    name = models.CharField(max_length=255)
    instruction = models.TextField()
    duration_days = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.conversation}"


# ---------- Shifokor xulosasi ----------
class DoctorSummary(models.Model):
    """
    Shifokor xulosasi model.
    """
    conversation = models.OneToOneField(
        Conversation, on_delete=models.CASCADE, related_name="doctor_summary"
    )
    operator = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="operator_summaries",
        null=True,
        blank=True,
    )
    diagnosis = models.TextField()
    recommendations = models.TextField()
    recommendations_list = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Summary for {self.conversation.title or self.conversation_id}"
