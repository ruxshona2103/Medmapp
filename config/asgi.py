import os
from django.core.asgi import get_asgi_application

# ⚠️ Birinchi bo‘lib DJANGO_SETTINGS_MODULE o‘rnatiladi
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Endi Django application initialize qilinadi
django_asgi_app = get_asgi_application()

# Keyin Channels import qilamiz
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import consultations.routing  # WebSocket routing

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(
            URLRouter(consultations.routing.websocket_urlpatterns)
        ),
    }
)
