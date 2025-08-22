from rest_framework import generics, permissions, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Application
from .serializers import ApplicationSerializer
from .permissions import IsDoctorOrAdmin


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
    """Superadmin, Admin, Operator yoki Shifokor Applicationsni boshqarishi uchun"""
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == "user":
            return Application.objects.filter(patient=user)
        return Application.objects.all()

    @action(detail=True, methods=["post"], permission_classes=[IsDoctorOrAdmin])
    def approve(self, request, pk=None):
        app = self.get_object()
        app.status = Application.STATUS_APPROVED
        app.save()
        return Response({"status": "Tasdiqlangan", "application_id": app.application_id})

    @action(detail=True, methods=["post"], permission_classes=[IsDoctorOrAdmin])
    def reject(self, request, pk=None):
        app = self.get_object()
        app.status = Application.STATUS_REJECTED
        app.save()
        return Response({"status": "Bekor qilingan", "application_id": app.application_id})

    @action(detail=True, methods=["post"], permission_classes=[IsDoctorOrAdmin])
    def processing(self, request, pk=None):
        app = self.get_object()
        app.status = Application.STATUS_PROCESSING
        app.save()
        return Response({"status": "Ko‘rib chiqilmoqda", "application_id": app.application_id})