from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
from core.models import Stage, Tag
from partners.models import Partner


class Patient(models.Model):
        GENDER_CHOICES = [("Erkak", "Erkak"), ("Ayol", "Ayol")]
        full_name = models.CharField(max_length=200)
        date_of_birth = models.DateField(null=True, blank=True)
        gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
        phone_number = models.CharField(max_length=20)
        email = models.EmailField(blank=True)
        complaints = models.TextField(blank=True)
        previous_diagnosis = models.TextField(blank=True)
        stage = models.ForeignKey(Stage, on_delete=models.SET_NULL, null=True, related_name="patients")
        tag = models.ForeignKey(Tag, on_delete=models.SET_NULL, null=True, blank=True, related_name="patients")
        created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,related_name="created_patients")
        is_archived = models.BooleanField(default=False)
        archived_at = models.DateTimeField(null=True, blank=True)
        avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name="Profil rasmi")
        assigned_partner = models.ForeignKey(
            Partner,
            on_delete=models.SET_NULL,
            null=True,
            blank=True,
            related_name='assigned_patients',
            verbose_name='Biriktirilgan hamkor',
            help_text='Operator tomonidan tanlanadi'
            )
        created_at = models.DateTimeField(
            auto_now_add=True,
            verbose_name='Yaratilgan vaqt',
            help_text='Bemor qachon yaratilgan'
        )

        updated_at = models.DateTimeField(
            auto_now=True,
            verbose_name='Yangilangan vaqt',
            help_text='Oxirgi yangilanish vaqti'
        )

        class Meta:
            verbose_name = 'Bemor'
            verbose_name_plural = 'Bemorlar'
            ordering = ['-created_at']  # Yangilar birinchi
            db_table = 'patients_patient'

        def __str__(self) -> str:
            return self.full_name


class PatientHistory(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="history")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class PatientDocument(models.Model):
    SOURCE_CHOICES = [("operator", "operator"), ("patient", "patient"), ("partner", "partner")]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="documents")
    file = models.FileField(
        upload_to="patient_documents/",
        validators=[FileExtensionValidator(allowed_extensions=["pdf", "jpg", "jpeg", "png", "doc", "docx"])],
    )
    description = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)

    class Meta:
        ordering = ["-uploaded_at"]


class ChatMessage(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to="chat_files/", blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]


# 5.1 (ixtiyoriy): Shartnoma tasdiqlash
class Contract(models.Model):
    STATUS = [("pending", "pending"), ("approved", "approved"), ("rejected", "rejected")]
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="contracts")
    file = models.FileField(upload_to="contracts/")
    status = models.CharField(max_length=20, choices=STATUS, default="pending")
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-id"]
