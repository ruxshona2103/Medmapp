"""
ASGI config for Medmapp project (WebSocket + HTTP support)
===========================================================

Bu fayl Django Channels uchun ASGI application ni sozlaydi.
- HTTP so'rovlar -> Django default ASGI handler
- WebSocket so'rovlar -> JWT Auth Middleware -> URLRouter

Production deployment:
    daphne -b 0.0.0.0 -p 8001 config.asgi:application

Docker deployment:
    command: daphne -b 0.0.0.0 -p 8001 config.asgi:application
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

# Django settings modulini sozlash (channels import qilishdan oldin!)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Django ASGI application (HTTP uchun)
django_asgi_app = get_asgi_application()

# Import WebSocket routing va JWT middleware
# MUHIM: get_asgi_application() dan keyin import qilish kerak!
from consultations.middleware import JWTAuthMiddleware
from config.routing import websocket_urlpatterns


# ============================================================
# ASGI APPLICATION (Production-Ready)
# ============================================================

application = ProtocolTypeRouter({
    # HTTP so'rovlar -> Django default handler
    "http": django_asgi_app,

    # WebSocket so'rovlar -> JWT Auth -> URL Routing -> Consumer
    "websocket": JWTAuthMiddleware(
        URLRouter(websocket_urlpatterns)
    ),
})
