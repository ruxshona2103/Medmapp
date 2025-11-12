# patients/signals.py

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from patients.models import Patient
from core.models import Stage, Tag

User = get_user_model()

def get_default_stage():
    return Stage.objects.order_by("id").first()

def get_default_tag():
    return Tag.objects.order_by("id").first()


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_patient_profile_on_user_create(sender, instance: User, created, **kwargs):
    """
    Faqat YANGI user va role == 'patient' bo'lsa
    Patient profil yaratadi.
    """
    if not created:
        return

    if getattr(instance, "role", None) != "patient":
        return

    Patient.objects.get_or_create(
        user=instance,
        defaults={
            "full_name": instance.get_full_name() or instance.phone_number,
            "phone_number": getattr(instance, "phone_number", "") or "",
            "email": getattr(instance, "email", "") or "",
            "gender": "Erkak",
            "stage": get_default_stage(),
            "tag": get_default_tag(),
        }
    )
