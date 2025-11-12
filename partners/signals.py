from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import Partner

User = get_user_model()

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_partner_profile_on_user_create(sender, instance: User, created, **kwargs):
    """
    Faqat YANGI yaratilgan user va role == 'partner' bo'lganda
    Partner profilini user=instance bilan yaratadi (idempotent).
    """
    if not created:
        return
    if getattr(instance, "role", None) != "partner":
        return

    Partner.objects.get_or_create(
        user=instance,
        defaults={
            # Modelingizda minimal talab qilingan maydonlar bo'lsa shu yerga qo‘ying.
        },
    )
