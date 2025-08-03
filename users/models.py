from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils.translation import gettext_lazy as _

class CustomUserManager(BaseUserManager):
    def create_user(self, phone, email=None, password=None,**extra_fields):
        if not phone:
            raise ValueError("Telefon raqam kiritilishi shart!!!")
        email - self.normalize_email(email)
        user = self.model(phone=phone, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(phone, email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    class Gender(models.TextChoices):
        MALE = 'male', _('Erkak')
        FEMALE = 'female', _('Ayol')

    ROLE_CHOICES = (
        ('patient', _('Bemor')),
        ('admin', _('Admin')),
        ('doctor', _('shifokor')),
        ('operator', _('Operator')),
    )

    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone = models.IntegerField(max_length=20, unique=True)
    email = models.EmailField(blank=True, null=True)
    birth_date = models.DateTimeField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices)
    role = models.CharField(max_length=25, choices=ROLE_CHOICES, default='patient')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = []


    def __str__(self):
        return f"{self.first_name}{self.last_name}"



























