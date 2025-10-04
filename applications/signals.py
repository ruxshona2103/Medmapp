from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Application, ApplicationHistory, Document

@receiver(post_save, sender=Application)
def create_application_history_on_creation(sender, instance, created, **kwargs):
    if created:
        comment = "Murojaat yaratildi"
        # Yaratuvchini `patient` yoki `created_by` (agar mavjud bo'lsa) orqali aniqlash
        author = instance.patient
        ApplicationHistory.objects.create(application=instance, author=author, comment=comment)

@receiver(post_save, sender=Document)
def create_document_upload_history(sender, instance, created, **kwargs):
    if created and instance.application:
        comment = f"Hujjat yuklandi: {instance.file.name.split('/')[-1]}"
        author = instance.uploaded_by or instance.application.patient
        ApplicationHistory.objects.create(application=instance.application, author=author, comment=comment)