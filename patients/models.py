from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator

User = get_user_model()


class Stage(models.Model):
    """Bemorning jarayon bosqichlari (masalan: Qabul, Tekshiruv, Operatsiya)."""

    title = models.CharField(max_length=50)
    code_name = models.CharField(max_length=20, unique=True)
    order = models.PositiveIntegerField(default=0)
    color = models.CharField(max_length=20, default="primary")

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.title


class Tag(models.Model):
    """Bemorlar uchun teglar (masalan: VIP, Qarzdor, Tezkor)."""

    name = models.CharField(max_length=20)
    color = models.CharField(max_length=20, default="primary")

    def __str__(self):
        return self.name


class PatientProfile(models.Model):
    """Foydalanuvchi bilan bog‘langan asosiy bemor profili (OneToOne)."""

    GENDER_CHOICES = [("male", "Erkak"), ("female", "Ayol")]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="patient_profile",
        verbose_name="Foydalanuvchi",
    )
    passport = models.CharField(max_length=20, null=True, blank=True)
    dob = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default="male")
    complaints = models.TextField(blank=True, default="")
    previous_diagnosis = models.TextField(blank=True, default="")
    full_name = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = "Bemor Profili"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.passport or 'Passportsiz'})"


class Patient(models.Model):
    """Jarayon bo‘yicha bemor yozuvi (Stage, Tag bilan)."""

    profile = models.OneToOneField(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name="patient_record",
        null=True,
        blank=True,
        verbose_name="Bemor profili",
    )
    full_name = models.CharField(max_length=200)
    phone = models.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                regex=r"^\+998\d{9}$",
                message="Telefon +998XXXXXXXXX ko‘rinishida bo‘lsin",
            )
        ],
    )
    email = models.EmailField(blank=True, null=True)
    region = models.CharField(max_length=100, blank=True, null=True)
    source = models.CharField(max_length=50, blank=True)
    stage = models.ForeignKey(
        Stage, on_delete=models.SET_NULL, null=True, blank=True, related_name="patients"
    )
    tag = models.ForeignKey(
        Tag, on_delete=models.SET_NULL, null=True, blank=True, related_name="patients"
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_patients",
    )
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bemor (Jarayon)"
        verbose_name_plural = "Bemorlar (Jarayon)"
        ordering = ["-created_at"]

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        if not self.full_name and self.profile and self.profile.user:
            self.full_name = (
                self.profile.user.get_full_name() or self.profile.user.phone_number
            )
        super().save(*args, **kwargs)


class PatientHistory(models.Model):
    """Bemor jarayonining tarixini yozib borish (kim o‘zgartirdi, nima dedi)."""

    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name="history"
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="patient_history", null=True
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tarix"
        verbose_name_plural = "Tarixlar"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.patient.full_name} - {self.comment[:30]}"


class PatientDocument(models.Model):
    """Bemor hujjatlari (fayllar)."""

    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name="documents", null=True
    )
    file = models.FileField(upload_to="patient_documents/")
    description = models.CharField(max_length=200, blank=True)
    uploaded_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="uploaded_documents", null=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    source_type = models.CharField(
        max_length=20,
        choices=[("operator", "Operator"), ("patient", "Bemor"), ("partner", "Hamkor")],
    )

    class Meta:
        verbose_name = "Hujjat"
        verbose_name_plural = "Hujjatlar"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.patient.full_name} - {self.file.name}"

    def get_source_type_display(self):
        return dict(self._meta.get_field("source_type").choices).get(
            self.source_type, self.source_type
        )
