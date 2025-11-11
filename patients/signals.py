# patients/signals.py
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from patients.models import Patient, PatientHistory
from core.models import Stage, Tag

User = get_user_model()


def get_default_stage():
    return Stage.objects.order_by("id").first()


def get_default_tag():
    return Tag.objects.order_by("id").first()


@receiver(post_save, sender=User)
def create_patient_profile(sender, instance, created, **kwargs):
    """
    ✅ Faqat role='patient' bo'lgan user uchun PatientProfile yaratadi.
    ✅ Partner, admin, operator — hech narsa yaratmaydi.
    """
    if not created or instance.role != "patient":
        return

    # ✅ Superadmin yoki tizim yaratgan bo‘lsa — created_by shunga yoziladi
    creator = User.objects.filter(role="superadmin").first()

    # ✅ Allaqachon Patient mavjud bo‘lsa – o‘tkazib yuboramiz
    if hasattr(instance, "patient_profile"):
        return

    stage = get_default_stage()
    tag = get_default_tag()

    patient = Patient.objects.create(
        user=instance,
        full_name=instance.get_full_name() or instance.phone_number,
        phone_number=instance.phone_number,
        email=instance.email or "",
        gender="Erkak",
        stage=stage,
        tag=tag,
        created_by=creator,
    )

    # ✅ Tarixga yozuv
    PatientHistory.objects.create(
        patient=patient,
        author=creator,
        comment="Avtomatik patient profili yaratildi.",
    )
    print("patient profii yaratildi")