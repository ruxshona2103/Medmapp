from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsOwner(BasePermission):
    """
    Foydalanuvchi faqat o'ziga tegishli obyektlarni ko'ra olishi uchun.
    """
    def has_object_permission(self, request, view, obj):
        user_id = getattr(request.user, "id", None)
        obj_user_id = getattr(obj, "user_id", None)
        return user_id is not None and obj_user_id == user_id


class HotelPermission(BasePermission):
    """
    Admin/SuperAdmin/Operator CRUD qilishi mumkin.
    Patient faqat ko'rishi mumkin.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return getattr(request.user, "is_authenticated", False) and getattr(request.user, "role", None) in ["admin", "superadmin", "operator"]


class BookingPermission(BasePermission):
    """
    Patient: faqat o'z buyurtmasini ko'ra oladi.
    Admin/Operator/SuperAdmin: hammasini ko'ra oladi va CRUD qilishi mumkin.
    """
    def has_object_permission(self, request, view, obj):
        role = getattr(request.user, "role", None)
        if role in ["admin", "superadmin", "operator"]:
            return True
        return getattr(obj, "user", None) == getattr(request.user, "id", None)
