"""
WebSocket URL Routing Configuration
====================================

Bu fayl WebSocket ulanishlari uchun URL routing ni belgilaydi.

STANDARDIZED URL Pattern:
    ws://localhost:8000/ws/chat/<conversation_id>/?token=eyJ0eXAi...

Production URL:
    wss://admin.medmapp.uz/ws/chat/<conversation_id>/?token=...

Security:
    - JWT token required via query parameter
    - Access control enforced in ChatConsumer
    - Rate limiting: 5 messages/second per user
    - XSS protection: HTML escaped before storage

Author: Senior Backend Developer (Medmapp Team)
Last Updated: 2025-12-31
"""

from django.urls import re_path
from consultations.consumers import ChatConsumer


# ============================================================
# WEBSOCKET URL PATTERNS (STANDARDIZED)
# ============================================================

websocket_urlpatterns = [
    # 1-on-1 Chat WebSocket
    # URL: ws://host/ws/chat/<conversation_id>/?token=...
    # Example: ws://localhost:8000/ws/chat/123/?token=eyJhbGc...
    re_path(
        r"^ws/chat/(?P<conversation_id>\d+)/$",
        ChatConsumer.as_asgi(),
        name="websocket_chat"
    ),
]

# ============================================================
# DEPRECATED PATTERNS (DO NOT USE)
# ============================================================
# OLD: ws/conversation/<conversation_id>/  (consultations/routing.py)
# Reason: Inconsistent with main routing, causes 404 errors
# Migrated to: ws/chat/<conversation_id>/
# ============================================================
