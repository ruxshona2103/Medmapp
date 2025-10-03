import random
import string
from django.db import models
from django.conf import settings
from patients.models import Patient
from stages.models import Stage

def generate_application_id():
    number = ''.join(random.choices(string.digits, k=5))
    return f"MED-{number}"

class Application(models.Model):
    STATUS_NEW = 'new'
    STATUS_PROCESSING = 'processing'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_NEW, "Yangi"),
        (STATUS_PROCESSING, "Ko‘rib chiqilmoqda"),
        (STATUS_APPROVED, "Tasdiqlangan"),
        (STATUS_REJECTED, "Bekor qilingan"),
    ]
    application_id = models.CharField(max_length=20, unique=True, default=generate_application_id, editable=False)
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="applications", verbose_name="Bemor")
    linked_patient = models.ForeignKey(Patient, on_delete=models.SET_NULL, null=True, blank=True, related_name="applications", verbose_name="Bemor Profili")  # Qo‘shildi
    clinic_name = models.CharField(max_length=255, verbose_name="Klinika nomi")
    complaint = models.TextField(verbose_name="Shikoyatlar")
    diagnosis = models.TextField(null=True, blank=True, verbose_name="Tashxis")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=STATUS_NEW, verbose_name="Holat")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")
    stage = models.ForeignKey(
        Stage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applications",
        verbose_name="Bosqich"
    )
    class Meta:
        verbose_name = "Ariza"
        verbose_name_plural = "Arizalar"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.application_id} – {self.patient.phone_number} ({self.get_status_display()})"

class ApplicationHistory(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="history")  # related_name qo‘shildi
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name="Muallif")
    comment = models.TextField(verbose_name="Izoh")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")

    class Meta:
        verbose_name = "Ariza Tarixi"
        verbose_name_plural = "Arizalar Tarixi"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.application.application_id} - {self.comment[:30]}"

# applications/models.py
class Document(models.Model):
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE,
        related_name="documents", verbose_name="Ariza",
        null=True, blank=True,
    )
    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.CASCADE,
        related_name="application_documents",  # 🔑 bu yerda unique nom
        verbose_name="Bemor",
        null=True, blank=True,
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Yuklagan foydalanuvchi"
    )
    source_type = models.CharField(
        max_length=50,
        choices=[("manual", "Qo‘lda"), ("system", "Tizim")],
        default="manual",
        null=True, blank=True,
    )
    file = models.FileField(upload_to="documents/", verbose_name="Fayl",null=True, blank=True,)
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Yuklangan sana",null=True, blank=True,)

    class Meta:
        verbose_name = "Hujjat"
        verbose_name_plural = "Hujjatlar"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"Hujjat {self.id} - Application {self.application.id}"
