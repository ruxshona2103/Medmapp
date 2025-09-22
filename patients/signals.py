# patients/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import PatientProfile

User = get_user_model()


@receiver(post_save, sender=User)
def create_patient_profile(sender, instance, created, **kwargs):
    """
    Agar foydalanuvchi ro'yxatdan o'tsa va roli 'user' yoki 'patient' bo'lsa — unga PatientProfile yaratiladi.
    """
    if created and getattr(instance, "role", "").lower() in ["user", "patient"]:
        full_name = f"{instance.first_name or ''} {instance.last_name or ''}".strip()
        PatientProfile.objects.create(
            user=instance,
            passport=None,
            full_name=full_name,
            dob=None,
            gender="male",
            complaints="",
            previous_diagnosis="",
        )


@receiver(post_save, sender=User)
def save_patient_profile(sender, instance, **kwargs):
    if hasattr(instance, "patient_profile"):
        instance.patient_profile.save()
