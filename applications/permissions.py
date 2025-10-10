from rest_framework import permissions

class IsAuthenticatedOrReadOnly(permissions.BasePermission):
    """
    Har qanday autentifikatsiyalangan foydalanuvchi POST/PUT/PATCH/Delete qila oladi.
    Auth bo‘lmaganlar faqat o‘qiydi.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated
