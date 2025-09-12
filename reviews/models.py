from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

User = settings.AUTH_USER_MODEL  # authentication.CustomUser


class Clinic(models.Model):
    name = models.CharField(max_length=255, unique=True)
    address = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=64, blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class DoctorClinic(models.Model):
    """
    Doctor -> Clinic bog'lanishi (CustomUser modelini o'zgartirmasdan).
    """
    doctor = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="doctor_clinic",
        limit_choices_to={"role": "doctor"},
    )
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="clinic_doctors")

    class Meta:
        unique_together = (("doctor", "clinic"),)

    def __str__(self):
        return f"{self.doctor} → {self.clinic}"


def review_video_upload_to(instance, filename):
    return f"reviews/videos/{instance.id or 'tmp'}/{filename}"


class Review(models.Model):
    """
    Review klinikaga yoki doktorga yoziladi (kamida bittasi).
    Author — odatda ROLE_USER (bemor).
    """
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="written_reviews",
    )
    clinic = models.ForeignKey(
        Clinic, on_delete=models.CASCADE, related_name="reviews",
        null=True, blank=True
    )
    doctor = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="doctor_reviews",
        null=True, blank=True, limit_choices_to={"role": "doctor"}
    )
    rating = models.PositiveSmallIntegerField()   # 1..5
    text = models.TextField(blank=True)
    video = models.FileField(upload_to=review_video_upload_to, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        if not (self.clinic or self.doctor):
            raise ValidationError("Clinic yoki Doctor’dan bittasini tanlang.")
        if not (1 <= int(self.rating) <= 5):
            raise ValidationError({"rating": "Bahoni 1–5 oralig‘ida kiriting."})

    def __str__(self):
        target = self.clinic or self.doctor
        return f"{self.author} → {target} [{self.rating}]"
