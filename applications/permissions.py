# applications/permissions.py

from rest_framework import permissions

class IsAdminOrOperatorOrReadOnly(permissions.BasePermission):
    """
    Faqat admin yoki operatorga obyektni o'zgartirishga ruxsat beradi.
    Boshqa barcha foydalanuvchilarga faqat o'qishga (GET, HEAD, OPTIONS) ruxsat beriladi.
    """
    def has_permission(self, request, view):
        # Agar so'rov "xavfsiz" metodlardan biri bo'lsa (GET, HEAD, OPTIONS),
        # barcha autentifikatsiyadan o'tgan foydalanuvchilarga ruxsat beramiz.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Agar so'rov o'zgartirish (POST, PUT, PATCH, DELETE) uchun bo'lsa,
        # faqat admin yoki operator rolidagi foydalanuvchilarga ruxsat beramiz.
        # `request.user.role` sizning User modelingizda mavjud deb hisoblanadi.
        if not request.user or not request.user.is_authenticated:
            return False

        return request.user.role in ['admin', 'operator']