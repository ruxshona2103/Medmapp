# consultations/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import Message, Conversation
from .serializers import MessageSerializer
from django.contrib.auth import get_user_model


User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.conversation_group_name = f"conversation_{self.conversation_id}"

        # Join conversation group
        await self.channel_layer.group_add(
            self.conversation_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.conversation_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json.get("message")
        user = self.scope["user"]

        if user.is_authenticated and message:
            conversation = await Conversation.objects.aget(id=self.conversation_id)
            msg = await Message.objects.acreate(
                conversation=conversation,
                sender=user,
                type="text",
                content=message
            )
            serialized_msg = MessageSerializer(msg).data

            # Send message to group
            await self.channel_layer.group_send(
                self.conversation_group_name,
                {
                    "type": "chat_message",
                    "message": serialized_msg
                }
            )

    async def chat_message(self, event):
        message = event["message"]

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            "message": message
        }))