from rest_framework.permissions import BasePermission, SAFE_METHODS
from .models import Conversation


class IsConversationParticipant(BasePermission):
    def has_object_permission(self, request, view, obj):
        conv = (
            obj if isinstance(obj, Conversation) else getattr(obj, "conversation", None)
        )
        if not conv:
            return False
        return conv.participants.filter(user=request.user).exists()


class IsMessageOwnerOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.sender_id == request.user.id


class IsDoctorParticipant(BasePermission):
    """Xulosa/retsept yozish faqat shu suhbatdagi DOCTOR’ga ruxsat."""

    def has_object_permission(self, request, view, obj):
        conv = (
            obj if isinstance(obj, Conversation) else getattr(obj, "conversation", None)
        )
        if not conv:
            return False
        return conv.participants.filter(user=request.user, role="doctor").exists()
