from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import PatientProfile, Patient

User = get_user_model()
# (99) 992-58-40

@receiver(post_save, sender=User)
def create_patient_profile(sender, instance, created, **kwargs):
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


# YANGI SIGNAL: PatientProfile yaratilganda, agar Patient yo‘q bo‘lsa, yaratamiz
@receiver(post_save, sender=PatientProfile)
def create_patient_record(sender, instance, created, **kwargs):
    """
    PatientProfile yaratilganda, unga bog‘langan Patient (Jarayon) rekordini avtomatik yaratamiz.
    Agar allaqachon mavjud bo‘lsa, hech nima qilmaydi.
    """
    if not hasattr(instance, "patient_record") or not instance.patient_record:
        full_name = (
            instance.full_name
            or instance.user.get_full_name()
            or instance.user.phone_number
        )
        Patient.objects.create(
            profile=instance,
            full_name=full_name,
            phone=instance.user.phone_number,
            email=instance.user.email,  # Agar email User’da bo‘lsa
            created_by=instance.user,  # Yaratuvchi o‘zi bo‘lsin
            # Default bosqich yoki teglar qo‘shish mumkin, masalan: stage=Stage.objects.first()
        )
