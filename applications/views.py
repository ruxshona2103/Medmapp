from prompt_toolkit.validation import ValidationError
from rest_framework import generics, permissions, viewsets, status
from rest_framework.decorators import action

from applications.models import Application, Document
from applications.serializers import ApplicationSerializer, DocumentSerializer


class ApplicationCreateView(generics.CreateAPIView):
    """Bemor yangi arizasini yuboradi"""
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(patient=self.request.user)


class ApplicationStatusView(generics.RetrieveAPIView):
    """Bemor oxirgi arizani statusini korishi mumkun bo'ladi"""
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return Application.objects.filter(patient=self.request.user).latest("created_at")

class ApplicationViewSet(viewsets.ModelViewSet):
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            # Swagger uchun bo'sh queryset qaytarish
            return Application.objects.none()

        user = self.request.user
        if not user.is_authenticated:
            return Application.objects.none()

        if getattr(user, 'role', None) == "user":
            return Application.objects.filter(patient=user)
        return Application.objects.all()

class DocumentCreateView(generics.CreateAPIView):
    """Bemor hujjat yuborishi uchun"""
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        application = Application.objects.filter(patient=self.request.user).last()
        if not application:
            raise ValidationError({"detail": "Avval ariza yaratishingiz kerak."})
        serializer.save(application=application)


class DocumentListView(generics.ListAPIView):
    """Hujjatlarni olish"""
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Document.objects.none()
        user = self.request.user
        if not user.is_authenticated:
            return Document.objects.none()
        if user.role == "user":
            return Document.objects.filter(application__patient=user)
        elif user.role in ["doctor", "admin", "operator"]:
            return Document.objects.all()
        return Document.objects.none()
