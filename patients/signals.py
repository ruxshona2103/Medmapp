# patients/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from stages.models import Stage
from .models import Patient, PatientProfile
from applications.models import Application
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

@receiver(post_save, sender=User)
def create_patient_profile(sender, instance, created, **kwargs):
    """
    Automatically create a PatientProfile when a User with role='user' is created.
    """
    if created and instance.role == "user":
        logger.info(f"Creating PatientProfile for new User {instance.id} ({instance.phone_number})")
        profile, created = PatientProfile.objects.get_or_create(
            user=instance,
            defaults={
                "full_name": instance.get_full_name() or instance.phone_number or "Noma'lum",
                "gender": "male",
                "complaints": "",
                "previous_diagnosis": "",
            }
        )
        if created:
            logger.info(f"Created PatientProfile: {profile.id} for User {instance.id}")
        else:
            logger.info(f"PatientProfile already exists for User {instance.id}")

receiver(post_save, sender=Application)
def create_patient_from_application(sender, instance, created, **kwargs):
    """
    Ariza yaratilganda, tegishli PatientProfile va Patient yozuvlari
    mavjudligini ta'minlaydi.
    """
    if created:
        user = instance.patient
        logger.info(f"Processing new Application {instance.id} for User {user.id}")

        # 1. PatientProfile'ni topamiz yoki yaratamiz
        profile, _ = PatientProfile.objects.get_or_create(
            user=user,
            defaults={
                "full_name": user.get_full_name() or user.phone_number,
                "complaints": instance.complaint or "",
                "previous_diagnosis": instance.diagnosis or "",
            }
        )

        # 2. Patient yozuvini topamiz yoki yaratamiz (lekin 'stage'siz)
        Patient.objects.get_or_create(
            profile=profile,
            defaults={
                "full_name": profile.full_name or user.get_full_name(),
                "phone": user.phone_number,
                "email": getattr(user, "email", None),
                "source": f"Application_{instance.id}",
                "created_by": user,
            }
        )
        logger.info(f"Ensured Patient record exists for profile {profile.id}")
