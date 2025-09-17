# patients/permissions.py
from rest_framework.permissions import BasePermission

def norm_role(user) -> str:
    raw = (getattr(user, 'role', '') or '').strip().lower()
    phone = getattr(user, 'phone_number', '').strip()

    # ✅ Telefon raqamingizni avtomatik superadmin qilish
    if phone == '+998910184880':
        return 'admin'

    mapping = {
        'user': 'patient',      # CustomUserdagi "user" = bemor
        'bemor': 'patient',
        'patient': 'patient',
        'operator': 'operator',
        'doctor': 'doctor',
        'admin': 'admin',
        'superadmin': 'admin',
        'partner': 'partner',
    }
    return mapping.get(raw, raw)


class IsOperatorOrHigher(BasePermission):
    def has_permission(self, request, view):
        return norm_role(request.user) in ('operator', 'admin', 'doctor')


class IsOwnerOrOperator(BasePermission):
    def has_object_permission(self, request, view, obj):
        r = norm_role(request.user)
        if r in ('admin', 'operator'):
            return True
        if hasattr(obj, 'user_id') and obj.user_id == getattr(request.user, 'id', None):
            return True
        return False


class IsContractOwnerOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        r = norm_role(request.user)
        if r in ('admin', 'operator'):
            return True
        prof = getattr(obj, 'patient_profile', None)
        return bool(prof and prof.user_id == getattr(request.user, 'id', None))
