from rest_framework import viewsets, permissions
from .models import Stage
from .serializers import StageSerializer

class IsAdminOrOperator(permissions.BasePermission):
    """Faqat admin yoki operatorlarga to'liq ruxsat beradi."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in ['admin', 'operator']


class StageViewSet(viewsets.ModelViewSet):
    """
    Bosqichlarni (Stages) boshqarish uchun API.
    Faqat Admin va Operatorlar uchun ruxsat berilgan.
    """
    queryset = Stage.objects.all()
    serializer_class = StageSerializer
    permission_classes = [IsAdminOrOperator]