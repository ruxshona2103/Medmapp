from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from .models import Stage, Tag
from .serializers import StageSerializer, TagSerializer

class StageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    TZ 3.3: Bosqichlar ro‘yxati.
    Faqat GET ishlaydi, tartib: order → id.
    """
    queryset = Stage.objects.all().order_by("order", "id")
    serializer_class = StageSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(operation_description="Barcha bosqichlar ro‘yxati (order bo‘yicha tartiblangan).")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class TagViewSet(viewsets.ModelViewSet):
    """
    TZ 3.2: Teglar API
    - GET /tags/ — barcha teglar ro‘yxati
    - POST /tags/ — yangi teg yaratish
    - DELETE /tags/{id}/ — tegni o‘chirish
    """
    queryset = Tag.objects.all().order_by("id")
    serializer_class = TagSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete"]

    @swagger_auto_schema(operation_description="Barcha teglar ro‘yxatini olish.")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(operation_description="Yangi teg yaratish.")
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(operation_description="Tegni o‘chirish (ID bo‘yicha).")
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
