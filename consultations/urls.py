

# consultations/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"conversations", views.ConversationViewSet, basename="conversation")
router.register(r"messages", views.MessageViewSet, basename="message")

urlpatterns = [
    path("", include(router.urls)),
]