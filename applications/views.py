from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser, FormParser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Application, ApplicationHistory, Document
from .permissions import IsAdminOrOperatorOrReadOnly
from .serializers import ApplicationSerializer, DocumentSerializer
from stages.models import Stage

from stages.models import Stage

class ApplicationViewSet(viewsets.ModelViewSet):
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOperatorOrReadOnly]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                name="stage",
                in_=openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                required=False,
                description="Bosqich (Stage) ID'si bo‘yicha filtrlash"
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        queryset = Application.objects.all()

        default_stage = Stage.objects.first()
        Application.objects.filter(stage__isnull=True).update(stage=default_stage)

        if getattr(user, 'role', 'user') == 'user':
            queryset = queryset.filter(patient=user)

        stage_id = self.request.query_params.get('stage')
        if stage_id:
            queryset = queryset.filter(stage__id=stage_id)

        return queryset.select_related('patient', 'stage').prefetch_related('documents', 'history')

    def perform_create(self, serializer):
      user = self.request.user
      default_stage = Stage.objects.filter(code_name='stage_default').first() or Stage.objects.first()

      serializer.save(
        patient=user,
        stage=serializer.validated_data.get('stage', default_stage)
    )


class DocumentListCreateView(generics.ListCreateAPIView):
    """
    Muayyan arizaga tegishli hujjatlarni olish (GET) va yangi hujjat yuklash (POST).
    """
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        application_id = self.kwargs.get("application_id")
        user = self.request.user

        if getattr(user, 'role', 'user') == 'user':
            return Document.objects.filter(application__id=application_id, application__patient=user)
        else:
            return Document.objects.filter(application__id=application_id)

    @swagger_auto_schema(
        operation_description="Tanlangan arizaga yangi fayl yuklash.",
        manual_parameters=[
            openapi.Parameter(name="file", in_=openapi.IN_FORM, type=openapi.TYPE_FILE, required=True, description="Tizimga yuklanadigan hujjat"),
        ],
        request_body=None
    )
    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def perform_create(self, serializer):
        application_id = self.kwargs.get("application_id")
        user = self.request.user
        query_params = {'id': application_id}

        if getattr(user, 'role', 'user') == 'user':
            query_params['patient'] = user

        application = get_object_or_404(Application, **query_params)
        serializer.save(application=application, uploaded_by=user)

class ChangeApplicationStageView(APIView):
    """Arizaning bosqichini o'zgartirish (faqat admin/operator uchun)."""
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["new_stage_id"],
            properties={
                "new_stage_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Yangi Stage ID"),
                "comment": openapi.Schema(type=openapi.TYPE_STRING, description="Izoh (ixtiyoriy)"),
            },
        )
    )
    def patch(self, request, application_id):
        user = request.user
        if getattr(user, 'role', 'user') not in ['admin', 'operator']:
            raise PermissionDenied("Sizda bosqichni o'zgartirishga ruxsat yo'q.")

        application = get_object_or_404(Application, id=application_id)
        new_stage_id = request.data.get("new_stage_id")
        if not new_stage_id:
            return Response({"error": "'new_stage_id' majburiy."}, status=status.HTTP_400_BAD_REQUEST)

        new_stage = get_object_or_404(Stage, id=new_stage_id)
        old_stage = application.stage
        application.stage = new_stage
        application.save(update_fields=["stage"])

        comment = request.data.get("comment", f"Bosqich o‘zgartirildi: {getattr(old_stage, 'name', '—')} → {new_stage.name}")
        ApplicationHistory.objects.create(application=application, author=user, comment=comment)

        return Response({"success": True, "new_stage": new_stage.name}, status=status.HTTP_200_OK)