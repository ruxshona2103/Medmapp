from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Patient
from .utils import get_default_stage, get_default_tag

User = get_user_model()

@receiver(post_save, sender=User)
def create_patient_on_user_register(sender, instance: User, created, **kwargs):
    if not created or getattr(instance, "role", None) != "patient":
        return

    stage = get_default_stage()
    tag = None  # yoki: get_default_tag()
    Patient.objects.get_or_create(
        created_by=instance,
        defaults={
            "full_name": (instance.get_full_name() or instance.username),
            "phone_number": getattr(instance, "phone_number", "") or "",
            "email": instance.email or "",
            "gender": "Erkak",
            "stage": stage,
            "tag": tag,
            "source": "Register",
        },
    )
