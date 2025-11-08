from rest_framework import viewsets, permissions
from drf_yasg.utils import swagger_auto_schema
from .models import Review, BlogPost
from .serializers import ReviewSerializer, BlogPostSerializer


# --------------------------------------------- REVIEWS --------------------------------------------------------
class IsSuperAdminOrReadOnly(permissions.BasePermission):
    """Superadmin uchun CRUD, boshqalar uchun faqat GET"""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_superuser


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsSuperAdminOrReadOnly]

    def get_queryset(self):
        qs = Review.objects.select_related("patient").all()
        # List uchun faqat tasdiqlangan sharhlar
        if self.action == "list":
            qs = qs.filter(is_approved=True)
        return qs

    @swagger_auto_schema(operation_summary="Tasdiqlangan fikrlar ro'yxati")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


# --------------------------------------------- BLOG -----------------------------------------------------------
class BlogPostViewSet(viewsets.ModelViewSet):
    queryset = BlogPost.objects.select_related("category").order_by("-created_at")
    serializer_class = BlogPostSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    @swagger_auto_schema(operation_summary="Blog maqolalari ro‘yxati (3 tilda)")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
