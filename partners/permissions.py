# partners/permissions.py
# ===============================================================
# HAMKOR PANEL - PERMISSIONS
# ===============================================================

from rest_framework import permissions


class IsPartnerUser(permissions.BasePermission):
    message = "Faqat hamkorlar uchun ruxsat etilgan."

    def has_permission(self, request, view):
        """User hamkormi?"""
        if not request.user or not request.user.is_authenticated:
            return False

        # User role'i partnermi?
        return getattr(request.user, 'role', None) == 'partner'

    def has_object_permission(self, request, view, obj):
        """Object-level permission"""
        if not request.user or not request.user.is_authenticated:
            return False

        # User role'i partner emasmi?
        if getattr(request.user, 'role', None) != 'partner':
            return False

        # Partner profilini olish
        from partners.models import Partner
        try:
            partner = Partner.objects.get(user=request.user)
        except Partner.DoesNotExist:
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
                getattr(request.user, 'role', None) == 'partner'
        )


class IsPartnerOrOperator(permissions.BasePermission):
    """
    Hamkor yoki Operator uchun ruxsat

    Faqat hamkor yoki operator/admin rolida bo'lgan userlar kirishlari mumkin.
    """

    message = "Faqat hamkorlar va operatorlar uchun ruxsat etilgan."

    def has_permission(self, request, view):
        """User hamkor yoki operatormi?"""
        if not request.user or not request.user.is_authenticated:
            return False

        # User role'i partner yoki operator/adminmi?
        role = getattr(request.user, 'role', None)
        return role in ('partner', 'operator', 'admin')