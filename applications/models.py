import random
import string
from django.db import models
from django.conf import settings

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
    clinic_name = models.CharField(max_length=255, verbose_name="Klinika nomi")
    complaint = models.TextField(verbose_name="Shikoyatlar")
    diagnosis = models.TextField(null=True, blank=True,  verbose_name="Tashxis")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=STATUS_NEW, verbose_name="Holat")
    created_at = models.DateTimeField(auto_now_add=True,verbose_name="Yaratilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")

    class Meta:
        verbose_name = "Ariza"
        verbose_name_plural = "Arizalar"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.application_id} – {self.patient.phone_number} ({self.get_status_display()})"


class Document(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="documents", verbose_name="Ariza")
    file = models.FileField(upload_to="documents/", verbose_name="Fayl")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Yuklangan sana')

    class Meta:
        verbose_name = "Hujjat"
        verbose_name_plural = "Hujjatlar"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"Hujjat {self.id} - Application {self.application.id}"
