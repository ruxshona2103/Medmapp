"""
WebSocket URL Routing Configuration
====================================

Bu fayl WebSocket ulanishlari uchun URL routing ni belgilaydi.

URL Pattern:
    ws://localhost:8001/ws/chat/<conversation_id>/?token=eyJ0eXAi...

Misol:
    ws://localhost:8001/ws/chat/123/?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

Author: Senior Backend Developer (Medmapp Team)
"""

from django.urls import re_path
from consultations.consumers import ChatConsumer


# ============================================================
# WEBSOCKET URL PATTERNS
# ============================================================

websocket_urlpatterns = [
    # 1-on-1 Chat WebSocket
    # URL: ws://host/ws/chat/<conversation_id>/?token=...
    re_path(
        r"^ws/chat/(?P<conversation_id>\d+)/$",
        ChatConsumer.as_asgi(),
        name="websocket_chat"
    ),
]
