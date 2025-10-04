from rest_framework import viewsets, permissions
from .models import Stage
from .serializers import StageSerializer
from rest_framework.response import Response

class IsAdminOrOperator(permissions.BasePermission):
    """Faqat admin yoki operatorlarga to'liq ruxsat beradi."""
    def has_permission(self, request, view):
        # Swagger generatsiyasi paytida xato chiqmasin
        if getattr(view, 'swagger_fake_view', False):
            return True

        user = request.user
        if not user or not user.is_authenticated:
            return False

        return getattr(user, 'role', None) in ['admin', 'operator']


class StageViewSet(viewsets.ModelViewSet):
    """
    Bosqichlarni (Stages) boshqarish uchun API.
    Faqat Admin va Operatorlar uchun ruxsat berilgan.
    """
    queryset = Stage.objects.all().order_by('order')
    serializer_class = StageSerializer
    permission_classes = [IsAdminOrOperator]

    def list(self, request, *args, **kwargs):
      stages = list(Stage.objects.all().order_by('id'))
      orders = [s.order for s in stages]

    # faqat 0 yoki dublikat bo‘lsa yangilash
      if all(o == 0 for o in orders) or len(set(orders)) != len(orders):
        for index, stage in enumerate(stages, start=1):
            Stage.objects.filter(pk=stage.pk).update(order=index)
        # print("✅ Stage orderlar avtomatik yangilandi")

      queryset = Stage.objects.all().order_by('order')
      serializer = self.get_serializer(queryset, many=True)
      return Response(serializer.data)

