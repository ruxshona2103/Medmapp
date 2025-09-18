# patients/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Patient, PatientProfile

@receiver(post_save, sender=Patient)
def create_patient_profile(sender, instance, created, **kwargs):
    if created:
        PatientProfile.objects.get_or_create(
            patient=instance,
            defaults={'gender': 'male'}
        )