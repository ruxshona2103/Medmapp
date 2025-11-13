# partners/permissions.py
# ===============================================================
# HAMKOR PANEL - PERMISSIONS
# ===============================================================

from rest_framework import permissions


class IsPartnerUser(permissions.BasePermission):
    """
    Hamkor foydalanuvchi uchun ruxsat

    Faqat hamkor profiliga ega bo'lgan userlar kirishlari mumkin.
    """

    message = "Faqat hamkorlar uchun ruxsat etilgan."

    def has_permission(self, request, view):
        """User hamkormi?"""
        if not request.user or not request.user.is_authenticated:
            return False

        # User'da partner_profile bormi?
        return hasattr(request.user, 'partner_profile')

    def has_object_permission(self, request, view, obj):
        """Object-level permission"""
        if not request.user or not request.user.is_authenticated:
            return False

        # Partner profilini olish
        try:
            partner = request.user.partner_profile
        except:
            return False

        # Patient object bo'lsa
        if hasattr(obj, 'assigned_partner'):
            return obj.assigned_partner == partner

        # PartnerResponseDocument object bo'lsa
        if hasattr(obj, 'partner'):
            return obj.partner == partner

        return False


class IsPartnerOrReadOnly(permissions.BasePermission):
    """
    Hamkor - to'liq huquq, boshqalar - faqat o'qish
    """

    def has_permission(self, request, view):
        """GET, HEAD, OPTIONS - hamma uchun"""
        if request.method in permissions.SAFE_METHODS:
            return True

        # POST, PUT, PATCH, DELETE - faqat hamkor
        return (
                request.user and
                request.user.is_authenticated and
                hasattr(request.user, 'partner_profile')
        )


class IsPartnerOrOperator(permissions.BasePermission):
    """
    Hamkor yoki Operator uchun ruxsat

    Faqat hamkor profiliga ega bo'lgan yoki operator/admin rolida bo'lgan
    userlar kirishlari mumkin.
    """

    message = "Faqat hamkorlar va operatorlar uchun ruxsat etilgan."

    def has_permission(self, request, view):
        """User hamkor yoki operatormi?"""
        if not request.user or not request.user.is_authenticated:
            return False

        # User'da partner_profile bormi yoki operator/adminmi?
        is_partner = hasattr(request.user, 'partner_profile')
        is_operator = hasattr(request.user, 'role') and request.user.role in ('operator', 'admin')

        return is_partner or is_operator