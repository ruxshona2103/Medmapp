from rest_framework import permissions


class IsOwner(permissions.BasePermission):

    def has_object_permission(self, request, view, obj):
        # obj may be Application, OrderedService, PatientProfile
        user = request.user
        if hasattr(obj, 'patient'):
            return obj.patient == user
        if hasattr(obj, 'application'):
            return obj.application.patient == user
        if hasattr(obj, 'user'):
            return obj.user == user
        return False