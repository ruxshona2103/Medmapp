# clinics/models.py
from django.db import models
from django.utils.text import slugify

# === Helpers ===
class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class TranslatedText(models.Model):
    title_uz = models.CharField(max_length=255)
    title_ru = models.CharField(max_length=255, blank=True, null=True)
    title_en = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        abstract = True

class TranslatedLong(models.Model):
    description_uz = models.TextField(blank=True, null=True)
    description_ru = models.TextField(blank=True, null=True)
    description_en = models.TextField(blank=True, null=True)

    class Meta:
        abstract = True


# === Geo ===
class Country(TranslatedText, TimeStamped):
    code = models.CharField(max_length=4, unique=True)  # "IN", "UZ" ...
    def __str__(self): return self.title_uz

class City(TranslatedText, TimeStamped):
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="cities")
    def __str__(self): return f"{self.title_uz} ({self.country.code})"


# === Reference ===
class Accreditation(models.Model):
    code = models.CharField(max_length=32, unique=True)  # "JCI", "NABH", ...
    name = models.CharField(max_length=64)
    def __str__(self): return self.name

class Specialty(TranslatedText, TranslatedLong, TimeStamped):
    icon = models.ImageField(upload_to="specialties/icons/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    def __str__(self): return self.title_uz


# === Clinic Core ===
class Clinic(TranslatedText, TranslatedLong, TimeStamped):
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="clinics")
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="clinics")
    address_uz = models.CharField(max_length=255)
    address_ru = models.CharField(max_length=255, blank=True, null=True)
    address_en = models.CharField(max_length=255, blank=True, null=True)

    # images
    cover_image = models.ImageField(upload_to="clinics/covers/", blank=True, null=True)      # card image
    background_image = models.ImageField(upload_to="clinics/headers/", blank=True, null=True)  # detail header

    # badges / metrics
    founded_year = models.PositiveIntegerField(blank=True, null=True)
    bed_count = models.PositiveIntegerField(blank=True, null=True)
    department_count = models.PositiveIntegerField(blank=True, null=True)
    operating_room_count = models.PositiveIntegerField(blank=True, null=True)

    rating = models.DecimalField(max_digits=3, decimal_places=2, blank=True, null=True)  # 4.8
    accreditations = models.ManyToManyField(Accreditation, blank=True, related_name="clinics")
    is_active = models.BooleanField(default=True)

    specialties = models.ManyToManyField(Specialty, through="ClinicSpecialty", related_name="clinics")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title_uz)[:240]
        super().save(*args, **kwargs)

    def __str__(self): return self.title_uz


class ClinicSpecialty(TimeStamped):
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE)
    specialty = models.ForeignKey(Specialty, on_delete=models.CASCADE)
    # optional: small custom description
    note_uz = models.CharField(max_length=255, blank=True, null=True)
    note_ru = models.CharField(max_length=255, blank=True, null=True)
    note_en = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        unique_together = ("clinic", "specialty")


# === Doctors ===
class Doctor(TimeStamped):
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="doctors")
    specialty = models.ForeignKey(Specialty, on_delete=models.SET_NULL, null=True, related_name="doctors")

    photo = models.ImageField(upload_to="doctors/photos/", blank=True, null=True)
    full_name = models.CharField(max_length=128)
    title_uz = models.CharField(max_length=128, blank=True, null=True)  # "Kardiojarroh"
    title_ru = models.CharField(max_length=128, blank=True, null=True)
    title_en = models.CharField(max_length=128, blank=True, null=True)

    experience_years = models.PositiveIntegerField(default=0)  # 27+
    work_time = models.CharField(max_length=64, blank=True, null=True)  # "08:30-17:30"

    is_top = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    def __str__(self): return self.full_name


# === Prices ===
class TreatmentPrice(TimeStamped):
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="prices")
    specialty = models.ForeignKey(Specialty, on_delete=models.PROTECT, related_name="prices")

    procedure_uz = models.CharField(max_length=255)
    procedure_ru = models.CharField(max_length=255, blank=True, null=True)
    procedure_en = models.CharField(max_length=255, blank=True, null=True)

    price_usd = models.DecimalField(max_digits=10, decimal_places=2)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("order", "id")


# === Infrastructure (left text list + optional right big image) ===
class ClinicInfrastructure(TimeStamped):
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="infrastructure")
    image = models.ImageField(upload_to="clinics/infrastructure/", blank=True, null=True)
    # bullet list item
    text_uz = models.CharField(max_length=255)
    text_ru = models.CharField(max_length=255, blank=True, null=True)
    text_en = models.CharField(max_length=255, blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("order", "id")


# === Gallery ===
class ClinicImage(TimeStamped):
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="gallery")
    image = models.ImageField(upload_to="clinics/gallery/")
    title_uz = models.CharField(max_length=255, blank=True, null=True)
    title_ru = models.CharField(max_length=255, blank=True, null=True)
    title_en = models.CharField(max_length=255, blank=True, null=True)
    description_uz = models.TextField(blank=True, null=True)
    description_ru = models.TextField(blank=True, null=True)
    description_en = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("order", "id")


# === Nearby guesthouse/hotel ===
class NearbyStay(TimeStamped):
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="nearby_stays")
    image = models.ImageField(upload_to="clinics/nearby/")
    title_uz = models.CharField(max_length=255)
    title_ru = models.CharField(max_length=255, blank=True, null=True)
    title_en = models.CharField(max_length=255, blank=True, null=True)
    description_uz = models.TextField(blank=True, null=True)
    description_ru = models.TextField(blank=True, null=True)
    description_en = models.TextField(blank=True, null=True)

    address = models.CharField(max_length=255)
    rating = models.DecimalField(max_digits=3, decimal_places=1, blank=True, null=True)  # 4.5

    def __str__(self): return self.title_uz


# === Jahon Klinikalari ===
class WorldClinic(TranslatedText, TranslatedLong, TimeStamped):
    """Jahon klinikalari - dunyo bo'ylab mashhur klinikalar"""
    image = models.ImageField(upload_to="world_clinics/", blank=True, null=True)
    famous_doctors_count = models.CharField(max_length=64, blank=True, null=True)  # "500+" yoki "1000+"
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="world_clinics", blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Jahon Klinikasi"
        verbose_name_plural = "Jahon Klinikalari"

    def __str__(self): return self.title_uz
