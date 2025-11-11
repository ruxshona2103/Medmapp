# consultations/consumers.py
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Message, Conversation
from .serializers import MessageSerializer
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
            self.conversation_group_name = f"conversation_{self.conversation_id}"
            self.user = self.scope.get("user")

            # User autentifikatsiya tekshiruvi
            if not self.user or not self.user.is_authenticated:
                logger.warning(f"Unauthenticated user tried to connect to conversation {self.conversation_id}")
                await self.close()
                return

            # Conversation mavjudligini va ruxsatni tekshirish
            has_access = await self.check_conversation_access()
            if not has_access:
                logger.warning(f"User {self.user.id} has no access to conversation {self.conversation_id}")
                await self.close()
                return

            # Join conversation group
            await self.channel_layer.group_add(
                self.conversation_group_name,
                self.channel_name
            )
            await self.accept()
            logger.info(f"User {self.user.id} connected to conversation {self.conversation_id}")

        except Exception as e:
            logger.error(f"Error in ChatConsumer.connect: {str(e)}", exc_info=True)
            await self.close()

    async def disconnect(self, close_code):
        try:
            if hasattr(self, 'conversation_group_name'):
                await self.channel_layer.group_discard(
                    self.conversation_group_name,
                    self.channel_name
                )
            logger.info(f"User disconnected from conversation {self.conversation_id}")
        except Exception as e:
            logger.error(f"Error in ChatConsumer.disconnect: {str(e)}", exc_info=True)

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message = text_data_json.get("message")

            if not message or not message.strip():
                await self.send(text_data=json.dumps({
                    "error": "Message content is required"
                }))
                return

            # Create message
            msg = await self.create_message(message)
            if msg:
                serialized_msg = await self.serialize_message(msg)

                # Send message to group
                await self.channel_layer.group_send(
                    self.conversation_group_name,
                    {
                        "type": "chat_message",
                        "message": serialized_msg
                    }
                )

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                "error": "Invalid JSON"
            }))
        except Exception as e:
            logger.error(f"Error in ChatConsumer.receive: {str(e)}", exc_info=True)
            await self.send(text_data=json.dumps({
                "error": "Internal server error"
            }))

    async def chat_message(self, event):
        message = event["message"]

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            "message": message
        }))

    @database_sync_to_async
    def check_conversation_access(self):
        """Foydalanuvchi suhbatga kirish huquqini tekshiradi"""
        try:
            conversation = Conversation.objects.get(id=self.conversation_id, is_active=True)
            return conversation.participants.filter(user=self.user).exists()
        except Conversation.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"Error checking conversation access: {str(e)}")
            return False

    @database_sync_to_async
    def create_message(self, content):
        """Yangi xabar yaratadi"""
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            msg = Message.objects.create(
                conversation=conversation,
                sender=self.user,
                type="text",
                content=content
            )
            return msg
        except Exception as e:
            logger.error(f"Error creating message: {str(e)}")
            return None

    @database_sync_to_async
    def serialize_message(self, msg):
        """Message ni serialize qiladi"""
        try:
            return MessageSerializer(msg).data
        except Exception as e:
            logger.error(f"Error serializing message: {str(e)}")
            return None
