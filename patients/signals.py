# patients/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Patient, PatientProfile, Stage
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

@receiver(post_save, sender=Application)
def create_patient_from_application(sender, instance, created, **kwargs):
    """
    Create or update Patient and PatientProfile when an Application is created.
    """
    if created:
        user = instance.patient
        logger.info(f"Processing new Application {instance.id} for User {user.id} ({user.phone_number})")

        # Create or get PatientProfile
        profile, profile_created = PatientProfile.objects.get_or_create(
            user=user,
            defaults={
                "full_name": user.get_full_name() or user.phone_number or "Noma'lum",
                "gender": "male",
                "complaints": instance.complaint or "",
                "previous_diagnosis": instance.diagnosis or "",
            }
        )
        if profile_created:
            logger.info(f"Created PatientProfile: {profile.id} for Application {instance.id}")
        else:
            logger.info(f"Using existing PatientProfile: {profile.id} for Application {instance.id}")

        # Create or get Patient
        stage = Stage.objects.filter(code_name=instance.status).first()
        patient, patient_created = Patient.objects.get_or_create(
            profile=profile,
            source=f"Application_{instance.id}",
            defaults={
                "full_name": profile.full_name or user.get_full_name() or "Noma'lum",
                "phone": user.phone_number,
                "email": getattr(user, "email", None),
                "created_by": user,
                "stage": stage,
            }
        )
        if patient_created:
            logger.info(f"Created Patient: {patient.id} for Application {instance.id}")
        else:
            patient.full_name = profile.full_name or user.get_full_name() or "Noma'lum"
            patient.stage = stage
            patient.save(update_fields=["full_name", "stage"])
            logger.info(f"Updated Patient: {patient.id} for Application {instance.id}")