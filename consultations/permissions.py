"""
Ruxsatlar (permissions) fayli.
"""
from rest_framework import permissions
from .models import Conversation, Participant


class IsConversationParticipant(permissions.BasePermission):
    """
    Foydalanuvchi suhbat ishtirokchisi ekanligini tekshiradi.
    """
    message = "Siz bu suhbat ishtirokchisi emassiz."

    def has_object_permission(self, request, view, obj):
        # Agar obj Conversation bo'lsa
        if isinstance(obj, Conversation):
            conv = obj
        else:
            # Aks holda conversation attributeni olamiz
            conv = getattr(obj, "conversation", None)

        if not conv:
            return False

        return conv.participants.filter(user=request.user).exists()


class IsMessageOwnerOrReadOnly(permissions.BasePermission):
    """
    Xabar egasi ekanligini tekshiradi yoki read-only ruxsat beradi.
    """
    message = "Siz faqat o'zingizning xabarlaringizni o'zgartira olasiz."

    def has_object_permission(self, request, view, obj):
        # Read-only metodlar uchun ruxsat
        if request.method in permissions.SAFE_METHODS:
            # Lekin conversation participant bo'lishi kerak
            conv = getattr(obj, "conversation", None)
            if conv:
                return conv.participants.filter(user=request.user).exists()
            return False

        # Write metodlar uchun faqat owner
        return obj.sender_id == request.user.id


class IsOperatorOrReadOnly(permissions.BasePermission):
    """
    Foydalanuvchi operator ekanligini tekshiradi.
    """
    message = "Siz operator emassiz."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user.is_staff or getattr(request.user, "is_operator", False)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            # Read access uchun conversation participant bo'lishi kerak
            conv = obj if isinstance(obj, Conversation) else getattr(obj, "conversation", None)
            if conv:
                return conv.participants.filter(user=request.user).exists()
            return False

        return request.user.is_staff or getattr(request.user, "is_operator", False)