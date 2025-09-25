from rest_framework import permissions


class IsDoctorOrAdmin(permissions.BasePermission):
    """Faqat doktor, admin operator yoki superadmin ruxsatga ega bolishi uhcun"""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in ["doctor", "admin", "operator", "superadmin"]
        )
