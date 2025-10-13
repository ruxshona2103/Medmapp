from rest_framework.permissions import BasePermission

class IsOperator(BasePermission):
    """Faqat operator yoki admin uchun ruxsat"""
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in ("operator", "admin"))
