# patients/views.py

import logging
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, NotFound
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model

from .models import Patient, PatientProfile, Stage, Tag, PatientHistory, PatientDocument
from .serializers import (
    PatientSerializer,
    PatientDetailSerializer,
    PatientCreateSerializer,
    StageSerializer,
    TagSerializer,
    PatientHistorySerializer,
    PatientDocumentSerializer,
    PatientProfileSerializer
)
from .permissions import IsOperatorOrHigher, IsOwnerOrOperator

User = get_user_model()
logger = logging.getLogger(__name__)


def _is_swagger(view) -> bool:
    """Swagger yoki oddiy requestni aniqlash"""
    return getattr(view, 'swagger_fake_view', False)


def _norm_role(u):
    role = getattr(u, 'role', '').lower()
    return 'patient' if role == 'user' else role


# ================================
# 1) Bemorlar ro'yxati (GET /patients/)
# ================================
class PatientListView(generics.ListAPIView):
    serializer_class = PatientSerializer
    permission_classes = [permissions.IsAuthenticated, IsOperatorOrHigher]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['stage', 'tag', 'created_by']

    def get_queryset(self):
        if _is_swagger(self) or not self.request.user.is_authenticated:
            return Patient.objects.none()

        user = self.request.user
        role = _norm_role(user)

        base = Patient.objects.select_related('stage', 'tag').prefetch_related('profile')

        if role == 'operator':
            return base.filter(created_by=user)
        if role in ('admin', 'doctor', 'superadmin'):
            return base

        raise PermissionDenied("Sizda bu sahifaga kirish huquqi yo'q.")


# ================================
# 2) Yangi bemor yaratish (POST /patients/create/)
# ================================
class PatientCreateView(generics.CreateAPIView):
    serializer_class = PatientCreateSerializer
    permission_classes = [permissions.IsAuthenticated, IsOperatorOrHigher]

    def perform_create(self, serializer):
        patient = serializer.save(created_by=self.request.user)
        PatientHistory.objects.create(
            patient=patient,
            author=self.request.user,
            comment="Bemor profili tizimga qo'shildi"
        )
        logger.info(f"Bemor yaratildi: {patient.full_name}")


# ================================
# 3) Bitta bemorni olish (GET /patients/{id}/)
# ================================
class PatientDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PatientDetailSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrOperator]

    def get_queryset(self):
        if _is_swagger(self) or not self.request.user.is_authenticated:
            return Patient.objects.none()

        user = self.request.user
        role = _norm_role(user)

        base = Patient.objects.select_related('stage', 'tag', 'profile') \
            .prefetch_related('history', 'documents')

        if role == 'operator':
            return base.filter(created_by=user)
        return base


# ================================
# 4) Bemor o'z profilini ko'radi (GET /patients/me/)
# ================================
class PatientMeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if _norm_role(user) != 'patient':
            raise PermissionDenied("Faqat bemorlar uchun.")

        try:
            profile = PatientProfile.objects.get(patient__user=user)
        except PatientProfile.DoesNotExist:
            raise NotFound("Sizning bemor profilingiz topilmadi.")

        serializer = PatientProfileSerializer(profile, context={"request": request})
        return Response(serializer.data)


# ================================
# 5) Bosqichni o'zgartirish (PATCH /patients/{id}/change-stage/)
# ================================
class ChangeStageView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrOperator]

    def patch(self, request, patient_id):
        patient = get_object_or_404(Patient, id=patient_id)
        self.check_object_permissions(request, patient)

        new_stage_id = request.data.get('new_stage_id')
        if not new_stage_id:
            return Response({"error": "'new_stage_id' majburiy."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            new_stage = Stage.objects.get(id=new_stage_id)
        except Stage.DoesNotExist:
            return Response({"error": "Bosqich topilmadi."}, status=status.HTTP_404_NOT_FOUND)

        old_stage = patient.stage
        patient.stage = new_stage
        patient.save(update_fields=['stage'])

        comment = request.data.get('comment') or f"Bosqich: {old_stage.title if old_stage else '—'} → {new_stage.title}"
        PatientHistory.objects.create(
            patient=patient,
            author=request.user,
            comment=comment
        )

        return Response({"success": True}, status=status.HTTP_200_OK)


# ================================
# 6) Hujjat yuklash (POST /patients/{id}/documents/)
# ================================
class PatientDocumentCreateView(generics.CreateAPIView):
    queryset = PatientDocument.objects.all()
    serializer_class = PatientDocumentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrOperator]

    def perform_create(self, serializer):
        patient = get_object_or_404(Patient, id=self.kwargs['patient_id'])
        self.check_object_permissions(self.request, patient)

        source_type = _norm_role(self.request.user)
        serializer.save(
            patient=patient,
            uploaded_by=self.request.user,
            source_type=source_type
        )


# ================================
# 7) Hujjatni o'chirish (DELETE /documents/{id}/)
# ================================
class PatientDocumentDeleteView(generics.DestroyAPIView):
    queryset = PatientDocument.objects.all()
    serializer_class = PatientDocumentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrOperator]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.check_object_permissions(request, instance)

        if instance.uploaded_by != request.user:
            raise PermissionDenied("Siz faqat o'zingiz yuklagan hujjatlarni o'chira olasiz.")

        filename = instance.file.name if instance.file else "unknown"
        self.perform_destroy(instance)
        logger.info(f"Hujjat o'chirildi: {filename}")
        return Response(status=status.HTTP_204_NO_CONTENT)


# ================================
# 8) Bosqichlar (GET /stages/, POST /stages/)
# ================================
class StageListView(generics.ListCreateAPIView):
    """
    GET: Barcha bosqichlar
    POST: Operator yoki admin yangi bosqich qo'sha oladi
    """
    queryset = Stage.objects.order_by('order')
    serializer_class = StageSerializer
    permission_classes = [permissions.IsAuthenticated, IsOperatorOrHigher]

    def post(self, request, *args, **kwargs):
        if _norm_role(request.user) not in ['operator', 'admin']:
            raise PermissionDenied("Faqat operator yoki admin bosqich qo'sha oladi.")
        return super().post(request, *args, **kwargs)


# ================================
# 9) Teglar (GET /tags/, POST /tags/, DELETE /tags/{id}/)
# ================================
class TagListView(generics.ListCreateAPIView):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated, IsOperatorOrHigher]


class TagDeleteView(generics.DestroyAPIView):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated, IsOperatorOrHigher]

    def destroy(self, request, *args, **kwargs):
        if _norm_role(request.user) not in ['admin', 'operator']:
            raise PermissionDenied("Faqat admin yoki operator teg o'chira oladi.")
        return super().destroy(request, *args, **kwargs)