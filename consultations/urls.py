

# consultations/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
router = DefaultRouter()
router.register(r"conversations", views.ConversationViewSet, basename="conversation")
router.register(r"messages", views.MessageViewSet, basename="message")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "conversations/operator/<int:patient_id>/messages/",
        views.ConversationViewSet.as_view(
            {
                "get": "operator_conversation_messages",
                "post": "operator_conversation_messages",
            }
        ),
        name="operator-conversation-messages",
    ),
]