from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Message, Conversation, ReadReceipt

@receiver(post_save, sender=Message)
def _update_last_message(sender, instance: Message, created, **kwargs):
    if created:
        Conversation.objects.filter(pk=instance.conversation_id)\
            .update(last_message_at=instance.created_at)
        # Sender uchun avtomatik read-receipt
        ReadReceipt.objects.get_or_create(message=instance, user=instance.sender)
        # Bu yerda WebSocket / Telegram notification trigger qilish mumkin.
        # (TZda ham bildirishnoma kerakligi aytilgan, keyin Celery task qo‘shib yuborish mumkin.)
