from rest_framework.permissions import BasePermission, SAFE_METHODS
from django.contrib.auth import get_user_model

User = get_user_model()

class IsPatientToCreate(BasePermission):
    """
    Faqat role='user' (bemor) POST/PUT/PATCH/DLETEga ruxsat (listing — hammaga).
    Kerak bo'lmasa, DRF default permissiondan foydalaning.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, "role", None) == "user"
