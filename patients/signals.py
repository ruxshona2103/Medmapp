from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import PatientProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_patient_profile(sender, instance, created, **kwargs):
    """
    Har bir yangi foydalanuvchi yaratilganda unga PatientProfile avtomatik qo‘shiladi.
    """
    if created and not hasattr(instance, "patient_profile") and instance.role == "user":
        # F.I.Sh. yig‘ib olish
        full_name = f"{instance.first_name or ''} {instance.last_name or ''}".strip()
        if not full_name:
            full_name = instance.phone_number

        PatientProfile.objects.create(
            user=instance,
            full_name=full_name,
            passport=None,
            dob="2000-01-01",
            gender="male",
            phone=instance.phone_number,
            email=instance.first_name.lower() + "@example.com" if instance.first_name else ""
        )
