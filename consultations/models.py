from django.conf import settings
from django.db import models
from django.utils import timezone
import os, mimetypes

User = settings.AUTH_USER_MODEL


# ---------- Asosiy suhbat ----------
class Conversation(models.Model):
    title = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="created_conversations"
    )
    patient = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="patient_conversations"
    )
    doctor = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="doctor_conversations"
    )
    is_active = models.BooleanField(default=True)
    last_message_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # Bitta bemor ↔ bitta shifokor uchun faqat bitta aktiv chatni saqlash:
        constraints = [
            models.UniqueConstraint(
                fields=["patient", "doctor"],
                name="uniq_patient_doctor_conversation",
            )
        ]
        ordering = ["-last_message_at", "-id"]

    def __str__(self) -> str:
        return self.title or f"Conversation #{self.pk}"


# ---------- Ishtirokchilar ----------
class Participant(models.Model):
    ROLE_CHOICES = (
        ("patient", "Patient"),
        ("doctor", "Doctor"),
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

    class Meta:
        unique_together = [("conversation", "user")]

    def __str__(self) -> str:
        return f"{self.user} in {self.conversation} as {self.role}"


# ---------- Xabarlar ----------
class Message(models.Model):
    TYPE_CHOICES = (("text", "Text"), ("file", "File"), ("system", "System"))

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="sent_messages"
    )
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="text")
    content = models.TextField(blank=True)
    reply_to = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="replies"
    )
    created_at = models.DateTimeField(default=timezone.now)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["conversation", "id"]),
            models.Index(fields=["sender", "id"]),
        ]

    def __str__(self) -> str:
        return f"Msg#{self.pk} in Conv#{self.conversation_id}"

    def soft_delete(self):
        """UI’da iz qoldirgan holda xabarni o‘chirib qo‘yish."""
        self.is_deleted = True
        self.content = ""
        self.save(update_fields=["is_deleted", "content"])


# ---------- Fayllar ----------
def chat_upload_path(instance: "Attachment", filename: str) -> str:
    # media/chat_attachments/2025/09/05/<id>_filename.ext
    return (
        f"chat_attachments/{timezone.now():%Y/%m/%d}/{instance.message_id}_{filename}"
    )


class Attachment(models.Model):
    message = models.ForeignKey(
        "Message", on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(upload_to=chat_upload_path)
    mime_type = models.CharField(max_length=100, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    original_name = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="chat_files"
    )
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-id"]

    def save(self, *args, **kwargs):
        # Fayldan metadata
        if self.file and not self.original_name:
            self.original_name = (
                os.path.basename(getattr(self.file, "name", "")) or self.original_name
            )
        if self.file and getattr(self.file, "size", None):
            self.size = self.file.size
        if not self.mime_type:
            ct = getattr(self.file, "content_type", "") if self.file else ""
            if not ct and self.original_name:
                ct = mimetypes.guess_type(self.original_name)[0] or ""
            self.mime_type = ct
        super().save(*args, **kwargs)


# ---------- O‘qilganini belgilash ----------
class ReadReceipt(models.Model):
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="read_receipts"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="message_reads"
    )
    read_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("message", "user")]
        indexes = [models.Index(fields=["user", "message"])]

    def __str__(self) -> str:
        return f"Read m#{self.message_id} by u#{self.user_id}"


# ---------- Shifokor xulosasi (1:1) ----------
class DoctorSummary(models.Model):
    conversation = models.OneToOneField(
        Conversation, on_delete=models.CASCADE, related_name="summary"
    )
    diagnosis = models.TextField(
        blank=True, help_text="Masalan: O'RVI, astenik sindrom"
    )
    recommendations = models.TextField(
        blank=True,
        help_text="Har satrda bitta tavsiya. UI ro‘yxatga ajratadi.",
    )
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="doctor_summaries"
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Summary for Conv#{self.conversation_id}"


# ---------- Retseptlar (N:1) ----------
class Prescription(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="prescriptions"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="prescriptions_authored"
    )
    name = models.CharField(max_length=255)  # Paratsetamol 500mg
    instruction = models.TextField(blank=True)  # 1 tabletka ×3, ovqatdan so'ng
    duration_days = models.PositiveIntegerField(
        null=True, blank=True
    )  # 7 kun, 10 kun...
    notes = models.TextField(blank=True)  # “Ehtiyojga qarab” va h.k.
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["conversation", "-id"])]

    def __str__(self) -> str:
        return f"{self.name} (Conv#{self.conversation_id})"
