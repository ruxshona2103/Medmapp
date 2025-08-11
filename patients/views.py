from rest_framework import generics , views, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.contrib.auth import get_user_model

from .models import PatientProfile, Application, Document, Service, OrderedService, ServiceStatusHistory
from .serializers import (PatientProfileSerializer, ApplicationSerializer, DocumentSerializer,
                          ServiceSerializer, OrderedServiceSerializer, ServiceStatusHistorySerializer)
from .permissions import IsOwner

User = get_user_model()

class CreateApplicationView(views.APIView):
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser)

    @transaction.atomic
    def post(self, request, format=None):
        data = request.data
        required = ["fullName", 'passport', 'dob', 'gender', 'phone', 'email', 'complaint']
        for f in required:
            if not data.get(f):
                return Response({"detail": f"Field '{f}' is required."}, status=status.HTTP_400_BAD_REQUEST)

    # Bemor profilini yaratish yoki yangilash
        profile_data = {k: data.get(k) for k in ['fullName', 'passport', 'dob', 'gender', 'phone', 'email']}
        profile, _ = PatientProfile.objects.update_or_create(user=request.user, defaults=profile_data)

class ApplicationStatusView(views.APIView):
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request, format = None):
        apps = Application.objects.filter(patient=request.user).order_by('-created_at')
        if not apps.exists():
            return Response({"status": None, "requestSent": False})
        latest = apps.first()
        return Response({"status": latest.status, "requestSent": True, "application_id": latest.id})

class ServiceListView(generics.ListAPIView):
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = ServiceSerializer
    queryset = Service.objects.all()

class OrderServiceView(views.APIView):
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request, format=None):
        service_id = request.data.get('service_id')
        data = request.data.get('data', None)
        if not service_id:
            return Response({"detail": "service_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        service = Service.objects.filter(service_id=service_id).first()
        if not service:
            return Response({"detail": "Bunday xizmat mavjud emas"}, status=status.HTTP_404_NOT_FOUND)

        # user anketani toldirganmi yoqmi tekshirish
        application = Application.objects.filter(patient=request.user).order_by('-created_at').first()
        if not application:
            return Response({"detail": "Avval anketani to'ldiring"}, status=status.HTTP_400_BAD_REQUEST)

        # xizmat buyurtma qilinganmi yoqmi tekshirish
        if OrderedService.objects.filter(application=application, service=service).exists():
            return Response({"detail": "Xizmat avval buyurtma qilingan"}, status=status.HTTP_400_BAD_REQUEST)

        ordered = OrderedService.objects.create(application=application, service=service, data=data)
        ServiceStatusHistory.objects.create(ordered_service=ordered, status_text='Order created')

        serializer = OrderedServiceSerializer(ordered)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class OrderedServicesListView(generics.ListAPIView):
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = OrderedServiceSerializer

    def get_queryset(self):
        return OrderedService.objects.filter(application__patient=self.request.user).select_related('service', 'application')
