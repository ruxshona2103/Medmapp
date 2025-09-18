# patients/models.py

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator, EmailValidator

User = get_user_model()


class Stage(models.Model):
    title = models.CharField(max_length=50)
    code_name = models.CharField(max_length=20, unique=True)  # new, response_letters, documents
    order = models.PositiveIntegerField(default=0)
    color = models.CharField(max_length=20, default="primary")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class Tag(models.Model):
    name = models.CharField(max_length=20)
    color = models.CharField(max_length=20, default="primary")

    def __str__(self):
        return self.name


class Patient(models.Model):
    """
    Bemor (kanban, holat, teg, tarix, hujjatlar)
    """
    full_name = models.CharField(max_length=200)
    phone = models.CharField(
        max_length=20,
        validators=[RegexValidator(regex=r"^\+998\d{9}$", message="Telefon +998XXXXXXXXX ko‘rinishida bo‘lsin")]
    )
    email = models.EmailField(blank=True)
    source = models.CharField(max_length=50, blank=True)

    stage = models.ForeignKey(Stage, on_delete=models.SET_NULL, null=True, blank=True, related_name="patients")
    tag = models.ForeignKey(Tag, on_delete=models.SET_NULL, null=True, blank=True, related_name="patients")

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_patients')
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bemor"
        verbose_name_plural = "Bemorlar"
        ordering = ["-created_at"]

    def __str__(self):
        return self.full_name


class PatientProfile(models.Model):
    """
    Shaxsiy ma'lumotlar (passport, tug'ilgan sana, jinsi)
    """
    GENDER_CHOICES = [("male", "Erkak"), ("female", "Ayol")]

    patient = models.OneToOneField(Patient, on_delete=models.CASCADE, related_name="profile")
    passport = models.CharField(max_length=20, unique=True, null=True, blank=True)
    dob = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    complaints = models.TextField(blank=True)
    previous_diagnosis = models.TextField(blank=True)

    class Meta:
        verbose_name = "Bemor Profili"

    def __str__(self):
        return f"{self.patient.full_name} - {self.passport}"


class PatientHistory(models.Model):
    """
    O'zgarishlar tarixi
    """
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="history")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="patient_history")
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tarix"
        verbose_name_plural = "Tarixlar"

    def __str__(self):
        return f"{self.patient.full_name} - {self.comment[:30]}"


class PatientDocument(models.Model):
    """
    Hujjatlar
    """
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="documents")
    file = models.FileField(upload_to="patient_documents/")
    description = models.CharField(max_length=200, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="uploaded_documents")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    source_type = models.CharField(max_length=20, choices=[
        ('operator', 'Operator'),
        ('patient', 'Bemor'),
        ('partner', 'Hamkor')
    ])

    class Meta:
        verbose_name = "Hujjat"
        verbose_name_plural = "Hujjatlar"

    def __str__(self):
        return f"{self.patient.full_name} - {self.file.name}"