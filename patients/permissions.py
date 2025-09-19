# patients/permissions.py

from rest_framework import permissions

class IsOperatorOrHigher(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['operator', 'admin', 'superadmin']

class IsOwnerOrOperator(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.role in ['admin', 'superadmin']:
            return True
        if request.user.role == 'operator' and obj.created_by == request.user:
            return True
        return False
