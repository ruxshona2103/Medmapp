from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator, EmailValidator

class PatientProfile(models.Model):
    GENDER_CHOICES = [
        ("male", "Erkak"),
        ("female", "Ayol"),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="patient_profile", verbose_name="Bemor")
    full_name = models.CharField(max_length=200, verbose_name="Ism-sharif")
    passport = models.CharField(max_length=20, unique=True, null=True, blank=True, verbose_name="Passport raqami")
    dob = models.DateTimeField(verbose_name="Tug'ilgan sana")
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, verbose_name="Jinsi")
    phone = models.CharField(max_length=20,
                             validators=[RegexValidator(regex=r"^\+998\d{9}$",
                                                        message="Telefon raqam +998 bilan boshlanishi va 13 ta belgidan iborat bo‘lishi kerak.")],
                             verbose_name="Telefon raqami"
                             )
    email = models.EmailField(max_length=100,
                              validators=[EmailValidator(message="Yaroqli email kiriting(@-belgisi bo'lishi kerak )")],
                              verbose_name="Elektron pochta"
                              )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Oxirgi yangilanish")

    class Meta:
        verbose_name = "Bemor Profili"
        verbose_name_plural = "Bemor Profillari"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name}"


