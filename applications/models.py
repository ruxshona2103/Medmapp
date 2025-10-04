import random
import string
from django.db import models
from django.conf import settings
from patients.models import Patient
from stages.models import Stage
# from clinics.models import Clinic  # agar keyin kerak bo‘lsa


def generate_application_id():
    number = ''.join(random.choices(string.digits, k=5))
    return f"MED-{number}"


class Application(models.Model):
    application_id = models.CharField(
        max_length=20,
        unique=True,
        default=generate_application_id,
        editable=False
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="applications",
        verbose_name="Bemor"
    )
    linked_patient = models.ForeignKey(
        Patient,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applications",
        verbose_name="Bemor Profili"
    )
    # clinic = models.ForeignKey(Clinic, on_delete=models.SET_NULL, null=True, blank=True, related_name="applications", verbose_name="Biriktirilgan Klinika")
    clinic_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Klinika nomi"
    )
    final_conclusion = models.TextField(
        null=True,
        blank=True,
        verbose_name="Yakuniy xulosa"
    )

    complaint = models.TextField(
        verbose_name="Shikoyatlar",
        null=True,
        blank=True
    )
    diagnosis = models.TextField(
        null=True,
        blank=True,
        verbose_name="Tashxis"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        null=True,
        blank=True,
        verbose_name="Yaratilgan vaqt"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        null=True,
        blank=True,
        verbose_name="Yangilangan vaqt"
    )
    stage = models.ForeignKey(
        Stage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applications",
        verbose_name="Bosqich"
    )

    class Meta:
        verbose_name = "Murojaat"
        verbose_name_plural = "Murojaatlar"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.application_id} – {self.patient.phone_number}"


class ApplicationHistory(models.Model):
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="history"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Muallif"
    )
    comment = models.TextField(verbose_name="Izoh")
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Yaratilgan vaqt"
    )

    class Meta:
        verbose_name = "Murojaat Tarixi"
        verbose_name_plural = "Murojaatlar Tarixi"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.application.application_id} - {self.comment[:30]}"


class Document(models.Model):
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name="Murojaat",
        null=True,
        blank=True
    )
    file = models.FileField(
    upload_to="application_documents/",
    verbose_name="Fayl",
    null=True,
    blank=True
)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    uploaded_at = models.DateTimeField(
    auto_now_add=True,
    null=True,
    blank=True,
    verbose_name="Yuklangan sana"
)

    class Meta:
        verbose_name = "Hujjat"
        verbose_name_plural = "Hujjatlar"
        ordering = ["-uploaded_at"]

    def __str__(self):
        if self.application:
            return f"Hujjat #{self.id} (Ariza #{self.application.application_id})"
        return f"Hujjat #{self.id}"
