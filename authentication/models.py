import random
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager,
)
from django.db import models


class CustomUserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, phone_number, password=None, role="user", **extra_fields):
        if not phone_number:
            raise ValueError("Telefon raqam kerak")
        phone_number = str(phone_number).strip()
        user = self.model(phone_number=phone_number, role=role, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, phone_number, password=None, role="user", **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(phone_number, password, role, **extra_fields)

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(
            phone_number, password, role="superadmin", **extra_fields
        )


class CustomUser(AbstractBaseUser, PermissionsMixin):
    ROLE_USER = "patient"
    ROLE_CLINIC = "clinic"
    ROLE_DOCTOR = "doctor"
    ROLE_OPERATOR = "operator"
    ROLE_ADMIN = "admin"
    ROLE_SUPERADMIN = "superadmin"
    ROLE_PARTNER = "partner"
    USERNAME_FIELD = "phone_number"

    ROLE_CHOICES = [
        (ROLE_USER, "Bemor"),
        (ROLE_CLINIC, "Klinika"),
        (ROLE_DOCTOR, "Shifokor"),
        (ROLE_OPERATOR, "Operator"),
        (ROLE_ADMIN, "Admin"),
        (ROLE_SUPERADMIN, "Super Admin"),
        (ROLE_PARTNER, "Partner"),
    ]

    first_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=20, unique=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_USER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def get_full_name(self):
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name if full_name else self.phone_number

    def __str__(self):
        return f"{self.phone_number} ({self.role})"


# registerda vaqtincha save qilib turish uchun
class PendingUser(models.Model):
    phone_number = models.CharField(max_length=20, unique=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=50, default="user")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()  # NOT NULL

    @classmethod
    def create_pending(cls, phone_number, first_name="", last_name="", district=""):
        return cls.objects.create(
            phone_number=phone_number,
            first_name=first_name,
            last_name=last_name,
            district=district,
            expires_at=timezone.now() + timedelta(minutes=5),
        )


class OTP(models.Model):
    user = models.ForeignKey(
        "authentication.CustomUser",
        on_delete=models.CASCADE,
        related_name="otps",
        null=True,
        blank=True,
    )
    phone_number = models.CharField(max_length=20, db_index=True)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["phone_number"])]
        verbose_name = "OTP"
        verbose_name_plural = "OTPs"

    def is_valid(self):
        return timezone.now() < self.expires_at

    @staticmethod
    def generate_code():
        return f"{random.randint(0, 999999):06d}"

    @classmethod
    def create_for_phone(cls, phone_number, ttl_seconds=300, user=None):
        code = cls.generate_code()
        now = timezone.now()
        expires = now + timedelta(seconds=ttl_seconds)
        return cls.objects.create(
            user=user, phone_number=phone_number, code=code, expires_at=expires
        )

    def __str__(self):
        target = self.user.phone_number if self.user else self.phone_number
        return f"OTP {self.code} for {target} (expires {self.expires_at.isoformat()})"


class MedicalFile(models.Model):
    user = models.ForeignKey(
        CustomUser, related_name="medical_files", on_delete=models.CASCADE
    )
    file = models.FileField(upload_to="medical_files/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Medical File"
        verbose_name_plural = "Medical Files"

    def __str__(self):
        return f"File for {self.user.phone_number} at {self.uploaded_at.isoformat()}"





class OperatorProfile(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='operator_profile',
        verbose_name='Foydalanuvchi'
    )
    full_name = models.CharField(max_length=255, verbose_name='To\'liq ism')
    employee_id = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Xodim ID',
        help_text='Masalan: "OP_001"'
    )
    department = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Bo\'lim'
    )
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='Telefon')
    email = models.EmailField(blank=True, null=True, verbose_name='Email')
    is_active = models.BooleanField(default=True, verbose_name='Faol')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Yaratilgan vaqt')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Yangilangan vaqt')

    class Meta:
        verbose_name = 'Operator Profili'
        verbose_name_plural = 'Operator Profillari'
        ordering = ['-created_at']
        db_table = 'authentication_operator_profile'

    def __str__(self):
        return f"{self.full_name} ({self.employee_id})"

    @property
    def total_patients_processed(self):
        from patients.models import PatientHistory
        return PatientHistory.objects.filter(author=self.user).count()

    @property
    def total_applications_processed(self):
        from applications.models import ApplicationHistory
        return ApplicationHistory.objects.filter(author=self.user).count()



