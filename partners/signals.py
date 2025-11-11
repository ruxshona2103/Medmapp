# partners/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from partners.models import Partner

User = get_user_model()


@receiver(post_save, sender=User)
def create_partner_profile(sender, instance, created, **kwargs):
    """
    ✅ Faqat role='partner' bo'lgan user uchun PartnerProfile yaratadi.
    ✅ Patient, operator, admin — umuman tegilmaydi.
    """
    if not created or instance.role != "partner":
        return

    # ✅ Allaqachon profil bo'lsa – yaratmaymiz
    if hasattr(instance, "partner_profile"):
        return

    Partner.objects.create(
        user=instance,
        name=instance.get_full_name() or instance.phone_number,
    )
    print("Partner profili yaratildi")
