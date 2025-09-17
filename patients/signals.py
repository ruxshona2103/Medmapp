# users/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import PatientProfile
from authentication.models import CustomUser

@receiver(post_save, sender=CustomUser)
def create_patient_profile_for_user(sender, instance, created, **kwargs):
    if created and instance.role == 'user':
        # Yangi foydalanuvchi va role='user' bo'lsa, profil yarat
        PatientProfile.objects.get_or_create(
            user=instance,
            defaults={
                'full_name': instance.first_name or instance.phone_number,
                'phone': instance.phone_number,
                'email': '',  # Ixtiyoriy, keyin to'ldiriladi
                'dob': None,  # Keyin to'ldiriladi
                'gender': 'male',  # Default, keyin o'zgartiriladi
            }
        )