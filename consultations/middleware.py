"""
JWT Authentication Middleware for Django Channels (WebSocket)
==============================================================

Bu middleware WebSocket ulanishlarida JWT token autentifikatsiyasini ta'minlaydi.

Ishlash tartibi:
1. Query string dan token ni oladi: ws://...?token=eyJ0eXAi...
2. Token ni SimpleJWT orqali decode qiladi
3. Foydalanuvchini bazadan topadi va scope['user'] ga joylashtiradi
4. Token yaroqsiz bo'lsa AnonymousUser ni qaytaradi

Xavfsizlik:
- Token expired bo'lsa avtomatik rad etiladi
- User.is_active=False bo'lsa rad etiladi
- Barcha xatolar logga yoziladi

Author: Senior Backend Developer (Medmapp Team)
"""

import logging
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from jwt import decode as jwt_decode
from django.conf import settings

# Logger sozlash
logger = logging.getLogger(__name__)
User = get_user_model()


class JWTAuthMiddleware(BaseMiddleware):
    """
    WebSocket JWT Authentication Middleware

    Usage:
        application = ProtocolTypeRouter({
            "websocket": JWTAuthMiddleware(
                URLRouter(websocket_urlpatterns)
            ),
        })
    """

    async def __call__(self, scope, receive, send):
        """
        Har bir WebSocket ulanishida ishga tushadi

        Args:
            scope (dict): WebSocket connection scope
            receive (callable): Message receiver
            send (callable): Message sender
        """
        # Query string dan token ni olish
        query_string = scope.get("query_string", b"").decode()
        token = self._extract_token(query_string)

        if token:
            # Token orqali foydalanuvchini autentifikatsiya qilish
            scope["user"] = await self._authenticate_user(token)
        else:
            # Token yo'q bo'lsa - AnonymousUser
            scope["user"] = AnonymousUser()
            logger.warning(
                f"WebSocket connection without token | "
                f"Path: {scope.get('path', 'unknown')}"
            )

        # Keyingi middleware yoki consumer ga o'tish
        return await super().__call__(scope, receive, send)

    def _extract_token(self, query_string: str) -> str | None:
        """
        Query string dan JWT token ni ajratib olish

        Args:
            query_string (str): "token=eyJ0eXAi...&other=value"

        Returns:
            str | None: Token yoki None
        """
        if not query_string:
            return None

        try:
            # Query parametrlarni parsing qilish
            params = parse_qs(query_string)
            # token parametri list qaytaradi: ['eyJ0eXAi...']
            token_list = params.get("token", [])
            return token_list[0] if token_list else None
        except Exception as e:
            logger.error(f"Error parsing query string: {e}")
            return None

    @database_sync_to_async
    def _authenticate_user(self, token: str):
        """
        JWT token orqali foydalanuvchini autentifikatsiya qilish

        Args:
            token (str): JWT access token

        Returns:
            User | AnonymousUser: Autentifikatsiya qilingan foydalanuvchi yoki AnonymousUser
        """
        try:
            # 1. Token ni decode qilish (UntypedToken - access/refresh farqi yo'q)
            UntypedToken(token)

            # 2. Token dan payload ni olish
            payload = jwt_decode(
                token,
                settings.SECRET_KEY,
                algorithms=["HS256"]
            )

            # 3. User ID ni olish
            user_id = payload.get("user_id")
            if not user_id:
                logger.warning("Token payload does not contain 'user_id'")
                return AnonymousUser()

            # 4. Foydalanuvchini bazadan olish
            user = User.objects.get(id=user_id)

            # 5. Foydalanuvchi aktiv ekanligini tekshirish
            if not user.is_active:
                logger.warning(f"Inactive user attempted WebSocket connection: {user.id}")
                return AnonymousUser()

            # 6. Muvaffaqiyatli autentifikatsiya
            logger.info(
                f"✅ WebSocket authenticated | User: {user.id} | "
                f"Role: {getattr(user, 'role', 'N/A')}"
            )
            return user

        except (InvalidToken, TokenError) as e:
            # Token yaroqsiz yoki muddati tugagan
            logger.warning(f"Invalid JWT token: {e}")
            return AnonymousUser()

        except User.DoesNotExist:
            # User bazada topilmadi
            logger.warning(f"User not found for token payload")
            return AnonymousUser()

        except Exception as e:
            # Kutilmagan xato
            logger.error(f"Unexpected error in JWT auth: {e}", exc_info=True)
            return AnonymousUser()
