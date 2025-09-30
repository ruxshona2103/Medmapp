"""
Ruxsatlar (permissions) fayli.
Bu faylda custom permission classlar aniqlanadi.
"""
from rest_framework import permissions
from .models import Conversation

class IsConversationParticipant(permissions.BasePermission):
    """
    Foydalanuvchi suhbat ishtirokchisi ekanligini tekshiradi.
    """
    def has_object_permission(self, request, view, obj):
        conv = (
            obj if isinstance(obj, Conversation) else getattr(obj, "conversation", None)
        )
        if not conv:
            return False
        return conv.participants.filter(user=request.user).exists()


class IsMessageOwnerOrReadOnly(permissions.BasePermission):
    """
    Xabar egasi ekanligini tekshiradi yoki read-only ruxsat beradi.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.sender_id == request.user.id


class IsDoctorParticipant(permissions.BasePermission):
    """
    Foydalanuvchi suhbatdagi doktor ekanligini tekshiradi.
    """
    def has_object_permission(self, request, view, obj):
        conv = (
            obj if isinstance(obj, Conversation) else getattr(obj, "conversation", None)
        )
        if not conv:
            return False
        return conv.participants.filter(user=request.user, role="doctor").exists()