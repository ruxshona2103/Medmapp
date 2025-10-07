from rest_framework.permissions import BasePermission

class IsOperatorOrAdmin(BasePermission):
    """Namunaviy permission: kerak bo'lsa kengaytirasiz."""
    def has_permission(self, request, view):
        role = getattr(getattr(request, "user", None), "role", None)
        return role in ["admin", "operator"]
