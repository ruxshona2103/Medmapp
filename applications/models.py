import random, string
from django.db import models
from django.conf import settings
from django.utils import timezone
from patients.models import Patient
from core.models import Stage


def generate_application_id():
    """Har bir ariza uchun unikal MED-XXXX identifikatori"""
    return f"MED-{''.join(random.choices(string.digits, k=5))}"


class Application(models.Model):
    """Application (Ariza) modeli — bemorning murojaati"""
    application_id = models.CharField(max_length=20, unique=True, default=generate_application_id, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="applications", verbose_name="Bemor")
    clinic_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Klinika nomi")
    complaint = models.TextField(blank=True, null=True, verbose_name="Shikoyatlar")
    diagnosis = models.TextField(blank=True, null=True, verbose_name="Tashxis")
    final_conclusion = models.TextField(blank=True, null=True, verbose_name="Yakuniy xulosa")
    stage = models.ForeignKey(Stage, on_delete=models.SET_NULL, null=True, blank=True, related_name="applications", verbose_name="Bosqich")
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Kutilmoqda"),
            ("approved", "Tasdiqlangan"),
            ("rejected", "Rad etilgan"),
        ],
        default="pending",
        verbose_name="Holat"
    )
    comment = models.TextField(blank=True, null=True, verbose_name="Izoh")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")
    is_archived = models.BooleanField(default=False, verbose_name="Arxivlanganmi")
    archived_at = models.DateTimeField(null=True, blank=True, verbose_name="Arxivlangan vaqt")

    class Meta:
        verbose_name = "Ariza"
        verbose_name_plural = "Arizalar"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.application_id} – {self.patient.full_name}"

    def archive(self):
        """Soft delete: Arizani arxivlash"""
        self.is_archived, self.archived_at = True, timezone.now()
        self.save(update_fields=["is_archived", "archived_at"])


class ApplicationHistory(models.Model):
    """Ariza tarixi (izohlar va o‘zgarishlar logi)"""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="history")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name="Muallif"
    )
    comment = models.TextField(verbose_name="Izoh")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")

    class Meta:
        verbose_name = "Ariza Tarixi"
        verbose_name_plural = "Arizalar Tarixi"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.application.application_id} - {self.comment[:30]}"


class Document(models.Model):
    """Arizaga biriktirilgan hujjatlar"""
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="documents", verbose_name="Ariza"
    )
    file = models.FileField(upload_to="application_documents/", verbose_name="Fayl")
    description = models.CharField(max_length=255, blank=True, null=True, verbose_name="Fayl tavsifi")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name="Yuklagan foydalanuvchi"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Yuklangan vaqt")

    class Meta:
        verbose_name = "Ariza Hujjati"
        verbose_name_plural = "Ariza Hujjatlari"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"Hujjat #{self.id} ({self.application.application_id})"
