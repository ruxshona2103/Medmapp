

"""
Consultations app signallari
============================

Bu faylda Conversation modeli uchun signal handlerlar joylashgan.
HTTP orqali status o'zgarganida, WebSocket orqali real-time bildirishnoma yuboriladi.

Vazifalar:
1. Conversation post_save signal - status o'zgarganda WebSocket ga broadcast yuborish
2. Message post_save signal - last_message_at ni yangilash
3. MessageReadStatus post_save signal - o'qilganlik holatini yangilash

Author: Senior Backend Developer (Medmapp Team)
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Conversation, Message, MessageReadStatus, Participant
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


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


@receiver(post_save, sender=Conversation)
def conversation_status_changed(sender, instance, created, **kwargs):
    """
    Conversation model saqlanganda ishlaydigan signal handler

    Args:
        sender: Conversation model class
        instance: Conversation obyekti
        created (bool): Yangi yaratildimi yoki yangilandi
        **kwargs: Qo'shimcha argumentlar (update_fields, raw, using, etc.)

    Vazifa:
        Status o'zgarganda yoki conversation yangilanganda,
        WebSocket orqali barcha ulangan clientlarga bildirishnoma yuborish

    WebSocket Message Format:
        {
            "type": "status_update",
            "conversation_id": 123,
            "status": "completed",  # yoki boshqa status
            "is_active": true,
            "updated_at": "2025-01-15T10:30:00Z"
        }
    """
    try:
        # Yangi yaratilgan conversation uchun signal ishlatilmaydi (faqat update)
        if created:
            logger.debug(
                f"✅ New conversation created | ID: {instance.id} | "
                f"No WebSocket broadcast needed for creation"
            )
            return

        # update_fields tekshiruvi - agar status o'zgarmagan bo'lsa, broadcast kerak emas
        update_fields = kwargs.get('update_fields')

        # Agar update_fields ko'rsatilgan bo'lsa va unda 'status' yoki 'is_active' yo'q bo'lsa, broadcast qilmaymiz
        if update_fields is not None:
            # Faqat status, is_active, title o'zgarganda broadcast qilamiz
            broadcast_fields = {'status', 'is_active', 'title'}
            if not broadcast_fields.intersection(update_fields):
                # Agar faqat boshqa fieldlar yangilangan bo'lsa (masalan, last_message_at)
                logger.debug(
                    f"⏭️  Conversation updated but no broadcast needed | ID: {instance.id} | "
                    f"Updated fields: {update_fields}"
                )
                return  # ✅ Broadcast qilmasdan chiqamiz

        # Channel Layer olish
        channel_layer = get_channel_layer()

        if not channel_layer:
            logger.error("❌ Channel layer not configured!")
            return

        # Redis group nomi pattern: chat_{conversation_id}
        group_name = f"chat_{instance.id}"

        # WebSocket ga yuboriladigan ma'lumot
        # Note: 'status' field hozirda Conversation modelida yo'q,
        # lekin kelajakda qo'shilganida getattr bilan xavfsiz olinadi
        status_value = getattr(instance, 'status', None)

        message_data = {
            "conversation_id": instance.id,
            "status": status_value,
            "is_active": instance.is_active,
            "last_message_at": instance.last_message_at.isoformat() if instance.last_message_at else None,
            "title": instance.title,
        }

        # Channel Layer orqali barcha group a'zolariga xabar yuborish
        # type: "status_update" - Consumer da status_update() method chaqiriladi
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "status_update",  # Consumer dagi method nomi (underscore bilan)
                "data": message_data
            }
        )

        logger.info(
            f"📡 WebSocket broadcast sent | "
            f"Group: {group_name} | "
            f"Conversation ID: {instance.id} | "
            f"Status: {status_value} | "
            f"Is Active: {instance.is_active}"
        )

    except Exception as e:
        # Signal ichida xatolik yuz bersa, asosiy amaliyot (HTTP save) buzilmasligi kerak
        logger.error(
            f"❌ Error in conversation_status_changed signal | "
            f"Conversation ID: {instance.id} | "
            f"Error: {e}",
            exc_info=True
        )
        # Signal xatolarini yutib yuboramiz, HTTP response fail bo'lmasin
        pass


