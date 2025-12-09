"""
WebSocket Chat Consumer for 1-on-1 Consultations
=================================================

Bu consumer Patient <-> Operator o'rtasidagi real-time chat ni boshqaradi.

Asosiy funksiyalar:
1. Connect: JWT autentifikatsiya, access control, Redis group ga qo'shilish
2. Receive: Xabar qabul qilish, DB ga saqlash, broadcast qilish
3. Disconnect: Redis group dan chiqish

Redis Group Pattern:
    chat_{conversation_id}

Xavfsizlik:
- Faqat autentifikatsiya qilingan foydalanuvchilar
- Faqat conversation ishtirokchilari kirishi mumkin
- Barcha xatolar logga yoziladi

Author: Senior Backend Developer (Medmapp Team)
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from .models import Message, Conversation
from .serializers import MessageSerializer

# Logger sozlash
logger = logging.getLogger(__name__)
User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    """
    1-on-1 Chat WebSocket Consumer

    URL Pattern:
        ws://host/ws/chat/<conversation_id>/?token=<jwt_token>

    Redis Group:
        chat_{conversation_id}

    Events:
        - chat_message: Yangi xabar broadcast qilish
        - typing_indicator: Typing ko'rsatgichi (future feature)
        - message_read: O'qilganlik belgisi (future feature)
    """
    async def connect(self):
        """
        WebSocket ulanish hodisasi

        Vazifalar:
        1. URL dan conversation_id ni olish
        2. Foydalanuvchi autentifikatsiyasini tekshirish
        3. Conversation access huquqini tekshirish
        4. Redis group ga qo'shilish
        5. Ulanishni qabul qilish

        Xavfsizlik:
        - AnonymousUser rad etiladi
        - is_active=False foydalanuvchilar rad etiladi
        - Conversation ishtirokchisi bo'lmagan foydalanuvchilar rad etiladi
        """
        try:
            # 1. URL parametrlarni olish
            self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
            self.room_group_name = f"chat_{self.conversation_id}"
            self.user = self.scope.get("user")

            # 2. Autentifikatsiya tekshiruvi
            if not self.user or isinstance(self.user, AnonymousUser):
                logger.warning(
                    f"❌ Unauthenticated connection attempt | "
                    f"Conversation: {self.conversation_id}"
                )
                await self.close(code=4001)  # Custom close code: Unauthorized
                return

            if not self.user.is_authenticated:
                logger.warning(
                    f"❌ Not authenticated | User: {self.user.id} | "
                    f"Conversation: {self.conversation_id}"
                )
                await self.close(code=4001)
                return

            # 3. Access control: Conversation ga kirish huquqini tekshirish
            has_access = await self._check_conversation_access()
            if not has_access:
                logger.warning(
                    f"❌ Access denied | User: {self.user.id} | "
                    f"Conversation: {self.conversation_id}"
                )
                await self.close(code=4003)  # Custom close code: Forbidden
                return

            # 4. Redis group ga qo'shilish
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )

            # 5. Ulanishni qabul qilish
            await self.accept()

            logger.info(
                f"✅ WebSocket connected | User: {self.user.id} | "
                f"Role: {getattr(self.user, 'role', 'N/A')} | "
                f"Conversation: {self.conversation_id} | "
                f"Group: {self.room_group_name}"
            )

        except KeyError as e:
            # URL parametr yo'q
            logger.error(f"❌ Missing URL parameter: {e}")
            await self.close(code=4000)  # Bad Request
        except Exception as e:
            # Kutilmagan xato
            logger.error(
                f"❌ Unexpected error in connect | "
                f"User: {getattr(self.user, 'id', 'unknown')} | "
                f"Error: {e}",
                exc_info=True
            )
            await self.close(code=4500)  # Internal Server Error

    async def disconnect(self, close_code):
        """
        WebSocket ulanish uzilish hodisasi

        Args:
            close_code (int): WebSocket close kodi

        Vazifalar:
        1. Redis group dan chiqish
        2. Logga yozish
        """
        try:
            # Redis group dan chiqish
            if hasattr(self, "room_group_name"):
                await self.channel_layer.group_discard(
                    self.room_group_name,
                    self.channel_name
                )

            logger.info(
                f"🔌 WebSocket disconnected | "
                f"User: {getattr(self.user, 'id', 'unknown')} | "
                f"Conversation: {getattr(self, 'conversation_id', 'unknown')} | "
                f"Close code: {close_code}"
            )

        except Exception as e:
            logger.error(
                f"❌ Error in disconnect | Error: {e}",
                exc_info=True
            )

    async def receive(self, text_data):
        """
        Clientdan xabar qabul qilish

        Args:
            text_data (str): JSON formatdagi xabar

        Expected JSON format:
            {
                "message": "Salom, doctor!",
                "type": "text"  # optional, default: "text"
            }

        Vazifalar:
        1. JSON ni parse qilish
        2. Xabarni validatsiya qilish
        3. DB ga saqlash
        4. Redis group ga broadcast qilish
        """
        try:
            # 1. JSON parsing
            data = json.loads(text_data)
            message_content = data.get("message", "").strip()
            message_type = data.get("type", "text")

            # 2. Validatsiya
            if not message_content:
                await self.send(text_data=json.dumps({
                    "error": "Message bo'sh bo'lishi mumkin emas",
                    "code": "EMPTY_MESSAGE"
                }))
                return

            if len(message_content) > 5000:  # Max 5000 characters
                await self.send(text_data=json.dumps({
                    "error": "Xabar juda uzun (max 5000 belgi)",
                    "code": "MESSAGE_TOO_LONG"
                }))
                return

            # 3. DB ga saqlash
            message_obj = await self._save_message(
                content=message_content,
                message_type=message_type
            )

            if not message_obj:
                await self.send(text_data=json.dumps({
                    "error": "Xabarni saqlashda xatolik",
                    "code": "SAVE_FAILED"
                }))
                return

            # 4. Message ni serialize qilish
            serialized_message = await self._serialize_message(message_obj)

            # 5. Redis group ga broadcast qilish
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": serialized_message
                }
            )

            logger.info(
                f"📨 Message sent | User: {self.user.id} | "
                f"Conversation: {self.conversation_id} | "
                f"Message ID: {message_obj.id}"
            )

        except json.JSONDecodeError:
            # JSON parse xatosi
            await self.send(text_data=json.dumps({
                "error": "Noto'g'ri JSON format",
                "code": "INVALID_JSON"
            }))
            logger.warning(
                f"❌ Invalid JSON received | User: {self.user.id} | "
                f"Data: {text_data[:100]}"
            )

        except Exception as e:
            # Kutilmagan xato
            logger.error(
                f"❌ Error in receive | User: {self.user.id} | "
                f"Error: {e}",
                exc_info=True
            )
            await self.send(text_data=json.dumps({
                "error": "Server xatosi",
                "code": "INTERNAL_ERROR"
            }))

    async def chat_message(self, event):
        """
        Redis group dan kelgan xabarni client ga yuborish

        Args:
            event (dict): {
                "type": "chat_message",
                "message": {...}  # Serialized message data
            }

        Bu method Redis channel layer orqali chaqiriladi.
        """
        message_data = event.get("message", {})

        # WebSocket orqali client ga yuborish
        await self.send(text_data=json.dumps({
            "type": "chat_message",
            "data": message_data
        }, ensure_ascii=False))

    async def status_update(self, event):
        """
        Conversation status o'zgarganida client ga bildirishnoma yuborish

        Args:
            event (dict): {
                "type": "status_update",
                "data": {
                    "conversation_id": 123,
                    "status": "completed",
                    "is_active": true,
                    "last_message_at": "2025-01-15T10:30:00Z",
                    "title": "Suhbat nomi"
                }
            }

        Bu method Redis channel layer orqali chaqiriladi.
        Signal dan conversation o'zgarganda avtomatik ishga tushadi.

        Flow:
        1. HTTP API orqali Operator conversation ni yangilaydi (status o'zgartiradi)
        2. Django Signal (post_save) ishga tushadi
        3. Signal Channel Layer ga xabar yuboradi
        4. Channel Layer bu method ni barcha ulangan clientlarda chaqiradi
        5. Client WebSocket orqali yangilangan ma'lumotni qabul qiladi

        WebSocket Response Format:
            {
                "type": "status_update",
                "data": {
                    "conversation_id": 123,
                    "status": "completed",
                    "is_active": true,
                    ...
                }
            }
        """
        status_data = event.get("data", {})

        # WebSocket orqali client ga yuborish
        await self.send(text_data=json.dumps({
            "type": "status_update",
            "data": status_data
        }, ensure_ascii=False))

        logger.info(
            f"✅ Status update sent to client | "
            f"User: {getattr(self.user, 'id', 'unknown')} | "
            f"Conversation: {status_data.get('conversation_id', 'unknown')} | "
            f"Status: {status_data.get('status', 'N/A')}"
        )

    # ============================================================
    # DATABASE OPERATIONS (sync -> async wrappers)
    # ============================================================

    @database_sync_to_async
    def _check_conversation_access(self):
        """
        Foydalanuvchi conversation ga kirish huquqini tekshiradi

        Returns:
            bool: True agar ruxsat bo'lsa, False aks holda

        Access Rules:
        - Conversation mavjud va aktiv bo'lishi kerak
        - Foydalanuvchi quyidagilardan biri bo'lishi kerak:
          1. Conversation.patient.user (bemor)
          2. Conversation.operator (operator)
          3. Participant.user (ishtirokchi via M2M)
        """
        try:
            # Conversation ni topish
            conversation = Conversation.objects.select_related(
                'patient', 'patient__user', 'operator'
            ).get(
                id=self.conversation_id,
                is_active=True
            )

            # 1. Check: Patient usermi?
            patient_user = getattr(conversation.patient, 'user', None)
            if patient_user and patient_user.id == self.user.id:
                logger.debug(f"✅ User {self.user.id} is patient of conversation {self.conversation_id}")
                return True

            # 2. Check: Operatormi?
            if conversation.operator and conversation.operator.id == self.user.id:
                logger.debug(f"✅ User {self.user.id} is operator of conversation {self.conversation_id}")
                return True

            # 3. Check: Participant via M2M table
            is_participant = conversation.participants.filter(
                user=self.user
            ).exists()

            if is_participant:
                logger.debug(f"✅ User {self.user.id} is M2M participant of conversation {self.conversation_id}")
                return True

            # ❌ Access denied
            logger.warning(
                f"❌ User {self.user.id} has NO relationship to conversation {self.conversation_id} | "
                f"Patient User: {patient_user.id if patient_user else 'None'} | "
                f"Operator: {conversation.operator.id if conversation.operator else 'None'} | "
                f"M2M Participants: {list(conversation.participants.values_list('user_id', flat=True))}"
            )
            return False

        except Conversation.DoesNotExist:
            logger.warning(f"Conversation {self.conversation_id} does not exist")
            return False
        except Exception as e:
            logger.error(f"Error checking conversation access: {e}", exc_info=True)
            return False

    @database_sync_to_async
    def _save_message(self, content: str, message_type: str = "text"):
        """
        Yangi xabarni DB ga saqlash

        Args:
            content (str): Xabar matni
            message_type (str): Xabar turi (text, image, file, etc.)

        Returns:
            Message | None: Yaratilgan message obyekti yoki None
        """
        try:
            # Conversation ni olish
            conversation = Conversation.objects.get(id=self.conversation_id)

            # Message yaratish
            message = Message.objects.create(
                conversation=conversation,
                sender=self.user,
                type=message_type,
                content=content
            )

            logger.debug(
                f"Message created | ID: {message.id} | "
                f"Sender: {self.user.id} | "
                f"Conversation: {self.conversation_id}"
            )

            return message

        except Conversation.DoesNotExist:
            logger.error(f"Conversation {self.conversation_id} not found")
            return None
        except Exception as e:
            logger.error(f"Error creating message: {e}", exc_info=True)
            return None

    @database_sync_to_async
    def _serialize_message(self, message):
        """
        Message obyektini JSON serializable formatga o'tkazish

        Args:
            message (Message): Message model instance

        Returns:
            dict: Serialized message data
        """
        try:
            return MessageSerializer(message).data
        except Exception as e:
            logger.error(f"Error serializing message: {e}", exc_info=True)
            return {
                "id": message.id,
                "content": message.content,
                "error": "Serialization failed"
            }
