from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator, EmailValidator, FileExtensionValidator


class Stage(models.Model):
    title = models.CharField(max_length=50)
    order = models.PositiveIntegerField(default=0)
    code_name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=20, default="primary")

    class Meta:
        verbose_name = 'Stage'
        verbose_name_plural = 'Stages'

    def __str__(self): return self.title

class Tag(models.Model):
    name = models.CharField(max_length=30)
    color = models.CharField(max_length=20, default="success")

    class Meta:
        verbose_name = 'Tag'
        verbose_name_plural = 'Tags'

    def __str__(self): return self.name

class PatientProfile(models.Model):
    GENDER_CHOICES = [("male", "Erkak"), ("female", "Ayol")]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patient_profile",
        verbose_name="Bemor foydalanuvchisi",
        limit_choices_to={'role': 'user'},   # <-- CustomUser ga mos!
    )
    full_name = models.CharField(max_length=200, verbose_name="Ism-sharif")
    passport = models.CharField(max_length=20, unique=True, null=True, blank=True, verbose_name="Passport raqami")
    dob = models.DateField(verbose_name="Tug'ilgan sana", null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, verbose_name="Jinsi")
    phone = models.CharField(
        max_length=20,
        validators=[RegexValidator(regex=r"^\+998\d{9}$", message="Telefon +998XXXXXXXXX ko‘rinishida bo‘lsin")],
        verbose_name="Telefon raqami",
    )
    email = models.EmailField(
        max_length=100,
        validators=[EmailValidator(message="Yaroqli email kiriting")],
        verbose_name="Elektron pochta",
        blank=True,
    )

    # Kanban atributlari (ixtiyoriy)
    stage = models.ForeignKey(Stage, on_delete=models.SET_NULL, null=True, blank=True, related_name="patient_profiles")
    tag   = models.ForeignKey(Tag, on_delete=models.SET_NULL, null=True, blank=True, related_name="patient_profiles")

    # Kim yaratgan (operator/admin/doctor)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_patients',
        verbose_name="Yaratgan foydalanuvchi",
    )

    # Avatar
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Oxirgi yangilanish")

    class Meta:
        verbose_name = "Bemor Profili"
        verbose_name_plural = "Bemor Profillari"
        ordering = ["-created_at"]

    def __str__(self): return self.full_name

class PatientHistory(models.Model):
    patient_profile = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='history')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'patient_history'
        ordering = ['-created_at']


class PatientDocument(models.Model):
    patient_profile = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='documents')
    file = models.FileField(upload_to='patient_documents/')
    description = models.CharField(max_length=200, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    source_type = models.CharField(
        max_length=20,
        choices=[
            ('operator', 'Operator'),
            ('patient', 'Bemor'),
            ('partner', 'Hamkor')
        ],
        default='operator'
    )

    class Meta:
        db_table = 'patient_documents'
        ordering = ['-uploaded_at']


class ChatMessage(models.Model):
    patient_profile = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='chat_files/', blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'chat_messages'
        ordering = ['timestamp']


class Contract(models.Model):
    patient_profile = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='contracts')
    file = models.FileField(upload_to='contracts/')
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Kutilmoqda'),
            ('approved', 'Tasdiqlandi'),
            ('rejected', 'Rad etildi')
        ],
        default='pending'
    )
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'contracts'
