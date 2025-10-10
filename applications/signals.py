from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Application, ApplicationHistory, Document


@receiver(post_save, sender=Application)
def create_application_history_on_creation(sender, instance, created, **kwargs):
    """
    Har safar yangi Application yaratilganda — tarixga yozuv qo‘shiladi.
    """
    if created:
        comment = "📝 Yangi murojaat yaratildi"
        # 👇 Patient modeli orqali foydalanuvchini aniqlaymiz
        author = instance.patient.created_by if hasattr(instance.patient, "created_by") else None

        # Faqat author mavjud bo‘lsa, tarixga yozamiz
        if author:
            ApplicationHistory.objects.create(
                application=instance,
                author=author,  # ✅ Bu endi CustomUser instance
                comment=comment
            )


@receiver(post_save, sender=Document)
def create_document_upload_history(sender, instance, created, **kwargs):
    """
    Har safar yangi hujjat yuklanganda — ApplicationHistory ga yozuv qo‘shiladi.
    """
    if created and instance.application:
        comment = f"📎 Hujjat yuklandi: {instance.file.name.split('/')[-1]}"

        # 👇 Authorni aniqlaymiz: uploaded_by mavjud bo‘lsa — undan, bo‘lmasa bemorning yaratuvchisidan
        if hasattr(instance, "uploaded_by") and instance.uploaded_by:
            author = instance.uploaded_by
        elif hasattr(instance.application.patient, "created_by"):
            author = instance.application.patient.created_by
        else:
            author = None

        if author:
            ApplicationHistory.objects.create(
                application=instance.application,
                author=author,  # ✅ CustomUser instance
                comment=comment
            )
