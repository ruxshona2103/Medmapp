# patients/signals.py

from django.conf import settings
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from patients.models import Patient
from core.models import Stage, Tag

User = get_user_model()

# Tag code_name va Application status orasidagi mapping
TAG_TO_STATUS_MAPPING = {
    'new': 'new',                    # Yangi
    'in_progress': 'in_progress',    # Jarayonda
    'completed': 'completed',        # Tugatilgan
    'rejected': 'rejected',          # Rad etilgan
}

# Tag name (title) ga asoslangan fallback mapping
TAG_NAME_TO_STATUS_MAPPING = {
    'yangi': 'new',
    'jarayonda': 'in_progress',
    'tugatilgan': 'completed',
    'rad etilgan': 'rejected',
}

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


def get_application_status_from_tag(tag):
    """
    Tag obyektiga asoslanib Application uchun mos status qaytaradi.

    Args:
        tag: Tag modeli obyekti

    Returns:
        str: Application status ('new', 'in_progress', 'completed', 'rejected')
        None: Agar mapping topilmasa
    """
    if not tag:
        return None

    # 1. code_name orqali tekshirish (priority)
    if tag.code_name and tag.code_name in TAG_TO_STATUS_MAPPING:
        return TAG_TO_STATUS_MAPPING[tag.code_name]

    # 2. name (title) orqali tekshirish (fallback)
    if tag.name:
        tag_name_lower = tag.name.lower().strip()
        if tag_name_lower in TAG_NAME_TO_STATUS_MAPPING:
            return TAG_NAME_TO_STATUS_MAPPING[tag_name_lower]

    # 3. Default: agar mapping topilmasa, 'new' qaytarish
    return None


@receiver(pre_save, sender=Patient)
def track_patient_tag_change(sender, instance, **kwargs):
    """
    Patient tag o'zgarishini kuzatish uchun oldingi tag qiymatini saqlaymiz.
    """
    if instance.pk:  # Faqat mavjud obyekt yangilanganda
        try:
            instance._old_tag_id = Patient.objects.get(pk=instance.pk).tag_id
        except Patient.DoesNotExist:
            instance._old_tag_id = None
    else:
        instance._old_tag_id = None


@receiver(post_save, sender=Patient)
def sync_applications_status_on_tag_change(sender, instance, created, **kwargs):
    """
    Patient ning tag maydoni o'zgarganda, uning barcha arizalarining
    status maydonini avtomatik yangilaydi.

    Misol:
    - Operator Patient.tag ni "Yangi" -> "Jarayonda" o'zgartirsa
    - Patient ning barcha Applications.status "new" -> "in_progress" o'zgaradi

    OPTIMIZATSIYA:
    - Faqat ariza ID larini oladi (to'liq obyekt emas) - memory efficient
    - ApplicationHistory ni batch-larda yaratadi - katta hajmlar uchun
    - Signal recursion va infinite loop dan himoyalangan
    """
    # Yangi yaratilgan patient uchun signal ishlamasin (faqat update)
    if created:
        return

    # Signal recursion ni oldini olish
    if getattr(instance, '_skip_application_sync', False):
        return

    # Tag o'zgarganligini tekshirish
    old_tag_id = getattr(instance, '_old_tag_id', None)
    new_tag_id = instance.tag_id

    if old_tag_id == new_tag_id:
        # Tag o'zgarmagan, status update qilmaymiz
        return

    # Yangi tag ga mos status topish
    new_status = get_application_status_from_tag(instance.tag)

    if not new_status:
        # Agar mapping topilmasa, hech narsa qilmaymiz
        return

    # Patient ning barcha arxivlanmagan arizalarini yangilash
    from applications.models import Application, ApplicationHistory

    # 1. MEMORY-EFFICIENT: Faqat ariza ID larini olish (to'liq obyekt emas!)
    application_ids = list(
        Application.objects.filter(
            patient=instance,
            is_archived=False
        ).values_list('id', flat=True)
    )

    if not application_ids:
        return

    # 2. Application statuslarini yangilash (.update() signal chaqirmaydi!)
    Application.objects.filter(id__in=application_ids).update(status=new_status)

    # 3. ApplicationHistory yozuvlarini batch-larda yaratish (memory-safe!)
    author = instance.created_by if hasattr(instance, 'created_by') else None
    comment = f"Status avtomatik yangilandi: Tag '{instance.tag.name}' ga moslab '{new_status}' holatga o'tkazildi."

    batch_size = 500  # Har 500 ta history bir vaqtda yaratiladi
    history_entries = []

    for app_id in application_ids:
        history_entries.append(
            ApplicationHistory(
                application_id=app_id,  # ← ID orqali bog'lash (obyekt yuklamas!)
                author=author,
                comment=comment
            )
        )

        # Batch to'lganda - bulk create qilish
        if len(history_entries) >= batch_size:
            ApplicationHistory.objects.bulk_create(
                history_entries,
                batch_size=batch_size,
                ignore_conflicts=True  # Duplicate yozuvlarni ignore qilish
            )
            history_entries = []  # List ni tozalash

    # Qolgan history entries ni yaratish
    if history_entries:
        ApplicationHistory.objects.bulk_create(
            history_entries,
            batch_size=batch_size,
            ignore_conflicts=True
        )
