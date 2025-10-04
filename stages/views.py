from rest_framework import viewsets, permissions
from .models import Stage
from .serializers import StageSerializer
from rest_framework.response import Response

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
    queryset = Stage.objects.all().order_by('order')
    serializer_class = StageSerializer
    permission_classes = [IsAdminOrOperator]

    def list(self, request, *args, **kwargs):
        """
        GET paytida bir marta order ni avtomatik to‘g‘rilaydi.
        """
        # Tekshiramiz: order hammasi 0 bo‘lsa yoki takror bo‘lsa
        stages = Stage.objects.all().order_by('id')
        orders = list(stages.values_list('order', flat=True))

        if all(o == 0 for o in orders) or len(set(orders)) != len(orders):
            # ✅ Agar birinchi marta noto‘g‘ri bo‘lsa, to‘g‘rilab chiqamiz
            for index, stage in enumerate(stages, start=1):
                stage.order = index
                stage.save(update_fields=['order'])
            print("✅ Stage orderlar avtomatik yangilandi")

        # Endi tartiblangan holda qaytaramiz
        queryset = Stage.objects.all().order_by('order')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
