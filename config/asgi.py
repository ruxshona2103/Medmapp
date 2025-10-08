import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_asgi_app = get_asgi_application()

# Agar websockets routing faylingiz bo‘lsa (masalan, consultations.routing.application yoki patients.routing.websocket_urlpatterns)
try:
    from consultations.routing import websocket_urlpatterns as chat_ws
except Exception:
    chat_ws = []

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(chat_ws)
    ),
})
