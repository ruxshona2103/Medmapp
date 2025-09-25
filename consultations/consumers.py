import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import Conversation, Message, MessageReadStatus, Participant
from .serializers import MessageSerializer


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = f"chat_{self.conversation_id}"

        # Foydalanuvchi suhbat ishtirokchisi ekanligini tekshirish
        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close()
            return

        if not await self.is_participant(user):
            await self.close()
            return

        # Guruhga qo‘shilish
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Onlayn holatini yangilash
        await self.update_participant_status(user, is_online=True)

    async def disconnect(self, close_code):
        # Guruhdan chiqish
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        # Offlayn holatini yangilash
        await self.update_participant_status(self.scope["user"], is_online=False)

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get("type")

        if message_type == "message":
            await self.handle_message(text_data_json)
        elif message_type == "typing":
            await self.handle_typing(text_data_json)
        elif message_type == "read":
            await self.handle_read(text_data_json)

    async def handle_message(self, data):
        user = self.scope["user"]
        content = data.get("content")
        reply_to_id = data.get("reply_to")
        message_type = data.get("message_type", "text")

        # Xabarni saqlash
        message = await self.save_message(
            user=user,
            conversation_id=self.conversation_id,
            content=content,
            reply_to_id=reply_to_id,
            message_type=message_type,
        )

        # Xabarni guruhga yuborish
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": MessageSerializer(
                    message, context={"request": self.scope}
                ).data,
            },
        )

    async def handle_typing(self, data):
        user = self.scope["user"]
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "typing_indicator",
                "user_id": user.id,
                "is_typing": data.get("is_typing", False),
            },
        )

    async def handle_read(self, data):
        user = self.scope["user"]
        message_id = data.get("message_id")
        await self.mark_message_read(user, message_id)

        # O‘qildi holatini guruhga yuborish
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "read_status", "message_id": message_id, "user_id": user.id},
        )

    async def chat_message(self, event):
        await self.send(
            text_data=json.dumps({"type": "message", "message": event["message"]})
        )

    async def typing_indicator(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "typing",
                    "user_id": event["user_id"],
                    "is_typing": event["is_typing"],
                }
            )
        )

    async def read_status(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "read",
                    "message_id": event["message_id"],
                    "user_id": event["user_id"],
                }
            )
        )

    @database_sync_to_async
    def is_participant(self, user):
        return Conversation.objects.filter(
            id=self.conversation_id, participants__user=user
        ).exists()

    @database_sync_to_async
    def save_message(
        self, user, conversation_id, content, reply_to_id=None, message_type="text"
    ):
        conversation = Conversation.objects.get(id=conversation_id)
        message_data = {
            "conversation": conversation,
            "sender": user,
            "type": message_type,
            "content": content,
        }
        if reply_to_id:
            message_data["reply_to"] = Message.objects.get(id=reply_to_id)
        message = Message.objects.create(**message_data)
        conversation.last_message_at = timezone.now()
        conversation.save(update_fields=["last_message_at"])
        return message

    @database_sync_to_async
    def mark_message_read(self, user, message_id):
        message = Message.objects.get(id=message_id)
        if message.sender != user:
            MessageReadStatus.objects.get_or_create(
                message=message, user=user, defaults={"read_at": timezone.now()}
            )
            message.mark_as_read(user)

    @database_sync_to_async
    def update_participant_status(self, user, is_online):
        participant = Participant.objects.filter(
            conversation__id=self.conversation_id, user=user
        ).first()
        if participant:
            participant.last_seen_at = (
                timezone.now() if is_online else participant.last_seen_at
            )
            participant.save(update_fields=["last_seen_at"])
