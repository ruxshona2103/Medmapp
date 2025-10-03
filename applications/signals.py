# applications/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Application, ApplicationHistory, Document
from django.contrib.auth import get_user_model

User = get_user_model()

@receiver(post_save, sender=Application)
def create_application_history(sender, instance, created, **kwargs):
    if created:
        comment = "Yangi ariza yaratildi"
        ApplicationHistory.objects.create(application=instance, author=instance.patient, comment=comment)

@receiver(post_save, sender=Document)
def create_document_history(sender, instance, created, **kwargs):
    if created:
        comment = f"Hujjat yuklandi: {instance.file.name}"
        ApplicationHistory.objects.create(application=instance.application, author=instance.application.patient, comment=comment)