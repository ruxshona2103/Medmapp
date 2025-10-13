from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Patient
from .utils import get_default_stage, get_default_tag

User = get_user_model()

@receiver(post_save, sender=User)
def create_patient_on_user_register(sender, instance: User, created, **kwargs):
    """Yangi ro‘yxatdan o‘tgan 'patient' uchun avtomatik Patient yozuvini yaratadi."""
    if not created or getattr(instance, "role", None) != "patient":
        return

    stage = get_default_stage()
    tag = get_default_tag()  # yoki None, agar teg kerak bo‘lmasa

    patient, was_created = Patient.objects.get_or_create(
        created_by=instance,
        defaults={
            "full_name": instance.get_full_name() or instance.username,
            "phone_number": getattr(instance, "phone_number", "") or "",
            "email": instance.email or "",
            "gender": "Erkak",
            "stage": stage,
            "tag": tag,
            "source": "Register",
        },
    )

    # Agar bu bemor yangidan yaratilgan bo‘lsa — tarixga yozuv qo‘shish mumkin
    if was_created:
        from applications.models import Stage
        from applications.models import Tag
        from patients.models import PatientHistory
        PatientHistory.objects.create(
            patient=patient,
            author=instance,
            comment="Mijoz ro‘yxatdan o‘tdi va avtomatik tarzda ‘Yangi’ bosqichga joylashtirildi."
        )
