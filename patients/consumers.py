import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from .models import Patient, ChatMessage

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.patient_id = self.scope["url_route"]["kwargs"]["patient_id"]
        self.room_group_name = f"chat_{self.patient_id}"
        user = self.scope.get("user", AnonymousUser())
        if not user or isinstance(user, AnonymousUser):
            await self.close()
            return
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        data = json.loads(text_data or "{}")
        typ = data.get("type")
        message = data.get("message")

        if typ == "chat_message" and message:
            msg = await self._save_message(self.scope["user"].id, self.patient_id, message)
            payload = {
                "sender": str(self.scope["user"]),
                "message": msg.message,
                "file_url": None,
                "timestamp": msg.timestamp.isoformat(),
            }
            await self.channel_layer.group_send(self.room_group_name, {"type": "chat.broadcast", "payload": payload})

    async def chat_broadcast(self, event):
        await self.send(text_data=json.dumps(event["payload"]))

    @database_sync_to_async
    def _save_message(self, user_id, patient_id, message):
        patient = Patient.objects.get(pk=patient_id)
        user = User.objects.get(pk=user_id)
        return ChatMessage.objects.create(patient=patient, sender=user, message=message)
