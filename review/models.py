from django.db import models
from patients.models import Patient
from django.utils import timezone

# --------------------------------------------- REVIEWS --------------------------------------------------------
class Review(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="review")
    text = models.TextField("Sharh matni")
    is_approved = models.BooleanField(default=False, verbose_name="Tasdiqlanganmi")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Sharh"
        verbose_name_plural = "Sharhlar"

    def __str__(self):
        return f"{self.patient.full_name if hasattr(self.patient, 'full_name') else self.patient} - {self.text[:40]}"


# --------------------------------------------- BLOG -----------------------------------------------------------
class BlogCategory(models.Model):
    name_uz = models.CharField(max_length=100)
    name_ru = models.CharField(max_length=100, blank=True, null=True)
    name_en = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = "Blog toifasi"
        verbose_name_plural = "Blog toifalari"

    def __str__(self):
        return self.name_uz


class BlogPost(models.Model):
    category = models.ForeignKey(BlogCategory, on_delete=models.SET_NULL, null=True, related_name="posts")

    title_uz = models.CharField(max_length=255)
    title_ru = models.CharField(max_length=255, blank=True, null=True)
    title_en = models.CharField(max_length=255, blank=True, null=True)

    description_uz = models.TextField("Qisqa tavsif (UZ)", blank=True, null=True)
    description_ru = models.TextField("Qisqa tavsif (RU)", blank=True, null=True)
    description_en = models.TextField("Qisqa tavsif (EN)", blank=True, null=True)

    content_uz = models.TextField("To‘liq matn (UZ)")
    content_ru = models.TextField("To‘liq matn (RU)", blank=True, null=True)
    content_en = models.TextField("To‘liq matn (EN)", blank=True, null=True)

    author = models.CharField(max_length=255)
    image = models.ImageField(upload_to="blog/images/")
    created_at = models.DateField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Blog maqola"
        verbose_name_plural = "Blog maqolalar"

    def __str__(self):
        return self.title_uz or self.title_ru or self.title_en or "Blog maqola"