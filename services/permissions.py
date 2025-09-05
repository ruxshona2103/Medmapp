from rest_framework.permissions import BasePermission, SAFE_METHODS

# foydalanuvchi faqat oziga tegishlilani kora olishi uchun 
class IsOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return getattr(obj, "user_id", None) == getattr(request.user, "id", None)

# Admin/SuperAdmin/Operator CRUD qilaa oladi  Patient faqat o‘qiy oladi.
class HotelPermission(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user.role in ["admin", "superadmin", "operator"]

# Patient  create, view faqat oz buyurtmasi. Admin/Operator hammasini korish
class BookingPermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in ["admin", "superadmin", "operator"]:
            return True
        return obj.user == request.user


