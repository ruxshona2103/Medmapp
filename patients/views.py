from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import (
    PatientProfile, Application, Document, Service,
    OrderedService, ServiceStatusHistory
)
from .serializers import (
    PatientProfileSerializer, ApplicationSerializer, DocumentSerializer,
    ServiceSerializer, OrderedServiceSerializer, ServiceStatusHistorySerializer
)

class PatientProfileViewSet(viewsets.ModelViewSet):
    queryset = PatientProfile.objects.all()
    serializer_class = PatientProfileSerializer

class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer

class ApplicationViewSet(viewsets.ModelViewSet):
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer

    @action(detail=True, methods=["post"], url_path="add-document")
    def add_document(self, request, pk=None):
        application = self.get_object()
        serializer = DocumentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(application=application)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer


class OrderedServiceViewSet(viewsets.ModelViewSet):
    queryset = OrderedService.objects.all()
    serializer_class = OrderedServiceSerializer

    @action(detail=True, methods=["post"], url_path="update-status")
    def update_status(self, request, pk=None):
        """Buyurtma xizmatining statusini o‘zgartirish"""
        ordered_service = self.get_object()
        serializer = ServiceStatusHistorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(ordered_service=ordered_service)
            ordered_service.current_status_index = ordered_service.status_history.count() - 1
            ordered_service.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ServiceStatusHistoryViewSet(viewsets.ModelViewSet):
    queryset = ServiceStatusHistory.objects.all()
    serializer_class = ServiceStatusHistorySerializer
