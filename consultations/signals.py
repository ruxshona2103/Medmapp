

# consultations/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Message, MessageReadStatus, Participant
from django.utils import timezone


@receiver(post_save, sender=Message)
def update_conversation_last_message(sender, instance: Message, created, **kwargs):
    if created and not instance.is_deleted:
        try:
            Conversation.objects.filter(pk=instance.conversation_id).update(
                last_message_at=instance.created_at
            )
        except:
            pass


@receiver(post_save, sender=MessageReadStatus)
def update_message_read_status(sender, instance: MessageReadStatus, created, **kwargs):
    if created:
        try:
            instance.message.is_read_by_recipient = True
            instance.message.save(update_fields=["is_read_by_recipient"])

            instance.message.conversation.last_message_at = timezone.now()
            instance.message.conversation.save(update_fields=["last_message_at"])

            participant = Participant.objects.filter(
                conversation=instance.message.conversation, user=instance.user
            ).first()
            if participant:
                participant.last_seen_at = timezone.now()
                participant.save(update_fields=["last_seen_at"])
        except Exception as e:
            print(f"Error updating read status: {e}")


