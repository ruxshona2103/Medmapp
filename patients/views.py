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

from .models import (
    PatientProfile,
    Stage,
    Tag,
    PatientHistory,
    PatientDocument,
    Contract,
)
from .serializers import (
    PatientProfileSerializer,
    PatientProfileCreateUpdateSerializer,
    PatientProfileWithDocumentsSerializer,
    PatientDocumentSerializer,
    StageSerializer,
    TagSerializer,
    ContractSerializer,
    PatientAvatarUploadSerializer, OperatorPatientCreateSerializer,
)
from .permissions import IsOperatorOrHigher, IsOwnerOrOperator, IsContractOwnerOrAdmin

User = get_user_model()
logger = logging.getLogger(__name__)


# ---------- Yordamchi funksiyalar ----------
def _is_swagger(view) -> bool:
    """Swagger/Fake view tekshiruvi"""
    return bool(getattr(view, 'swagger_fake_view', False))


def _norm_role(u) -> str:
    """
    Foydalanuvchi rolini normalize qilish.
    'user' -> 'patient'
    """
    role = getattr(u, 'role', '').lower().strip()
    return 'patient' if role == 'user' else role


# ================================
# 1) Bemorlar ro'yxati (Operator/Admin)
# ================================
# ================================
# 1) Bemorlar ro'yxati (Operator/Admin)
# ================================
class PatientListCreateView(generics.ListCreateAPIView):
    """
    GET: Barcha bemorlar (admin/doctor/superadmin), faqat o'zi yaratganlar (operator)
    POST: Operator yangi bemor yaratadi (created_by = request.user)
    """
    permission_classes = [permissions.IsAuthenticated, IsOperatorOrHigher]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['created_by', 'stage', 'tag']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return OperatorPatientCreateSerializer  # yangi serializer
        return PatientProfileSerializer  # GET uchun

    def get_queryset(self):
        if _is_swagger(self) or not self.request.user.is_authenticated:
            return PatientProfile.objects.none()

        user = self.request.user
        role = _norm_role(user)

        base = (PatientProfile.objects
                .select_related('user', 'created_by', 'stage', 'tag')
                .prefetch_related('documents', 'history', 'messages'))

        if role == 'operator':
            return base.filter(created_by=user)
        if role in ('admin', 'doctor', 'superadmin'):
            return base

        raise PermissionDenied("Sizda bu sahifaga kirish huquqi yo'q.")

    def perform_create(self, serializer):
        profile = serializer.save(created_by=self.request.user)
        PatientHistory.objects.create(
            patient_profile=profile,
            author=self.request.user,
            comment="Bemor profili tizimga qo‘shildi"
        )
        logger.info(f"Bemor profili yaratildi: {profile.full_name} by {self.request.user}")

# ================================
# 2) Bemor o‘z profilini ko‘rishi (me)
# ================================
class PatientMeView(APIView):
    """
    GET: Bemor o'z profilini oladi. Yo'q bo'lsa — avtomatik yaratiladi.
    PATCH: Bemor o'z ma'lumotlarini yangilaydi.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if _norm_role(user) != 'patient':
            raise PermissionDenied("Faqat bemorlar uchun.")

        profile, created = PatientProfile.objects.get_or_create(
            user=user,
            defaults={
                'full_name': f"{user.first_name or ''} {user.last_name or ''}".strip() or user.phone_number,
                'phone': user.phone_number,
                'email': '',
                'gender': 'male',
                'dob': None,
                'passport': None,
            }
        )

        if created:
            PatientHistory.objects.create(
                patient_profile=profile,
                author=user,
                comment="Bemor profili avtomatik ravishda yaratildi"
            )
            logger.info(f"Avtomatik profil yaratildi: {profile.full_name} (user={user.phone_number})")

        serializer = PatientProfileSerializer(profile, context={"request": request})
        return Response(serializer.data)

    def patch(self, request):
        user = request.user
        if _norm_role(user) != 'patient':
            raise PermissionDenied("Faqat bemor o'z ma'lumotlarini yangilay oladi.")

        try:
            profile = PatientProfile.objects.get(user=user)
        except PatientProfile.DoesNotExist:
            # Qayta urinish
            raise NotFound("Profil topilmadi. Avval GET /me/ chaqiring.")

        serializer = PatientProfileCreateUpdateSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Tarixga yozamiz
        changes = "; ".join([f"{k}={v}" for k, v in serializer.validated_data.items()])
        PatientHistory.objects.create(
            patient_profile=profile,
            author=user,
            comment=f"Profil yangilandi: {changes}"
        )

        return Response(PatientProfileSerializer(profile, context={"request": request}).data)


# ================================
# 2.1) Bemor o‘zi avatar qo‘yish / o‘chirish
# ================================
class PatientMeAvatarView(APIView):
    """
    PATCH: avatar yuklash (multipart/form-data)
    DELETE: avatarni o'chirish
    """
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        try:
            profile = PatientProfile.objects.get(user=request.user)
        except PatientProfile.DoesNotExist:
            raise NotFound("Profil topilmadi. Avval GET /me/ chaqiring.")

        serializer = PatientAvatarUploadSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        logger.info(f"Avatar yangilandi: {request.user.phone_number}")
        return Response(PatientProfileSerializer(profile, context={"request": request}).data)

    def delete(self, request):
        try:
            profile = PatientProfile.objects.get(user=request.user)
        except PatientProfile.DoesNotExist:
            return Response(status=status.HTTP_204_NO_CONTENT)

        if profile.avatar:
            profile.avatar.delete(save=False)
            profile.avatar = None
            profile.save(update_fields=["avatar"])
            logger.info(f"Avatar o'chirildi: {request.user.phone_number}")

        return Response(status=status.HTTP_204_NO_CONTENT)


# ================================
# 2.2) Operator/Admin bemor avatarini boshqarish
# ================================
class PatientAvatarView(APIView):
    """
    PATCH /api/patients/<pk>/avatar/
    DELETE /api/patients/<pk>/avatar/
    """
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrOperator]

    def get_object(self, pk):
        return get_object_or_404(PatientProfile.objects.select_related("user"), pk=pk)

    def patch(self, request, pk):
        profile = self.get_object(pk)
        self.check_object_permissions(request, profile)

        serializer = PatientAvatarUploadSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        logger.info(f"Operator tomonidan avatar yangilandi: {profile.user.phone_number}")
        return Response(PatientProfileSerializer(profile, context={"request": request}).data)

    def delete(self, request, pk):
        profile = self.get_object(pk)
        self.check_object_permissions(request, profile)

        if profile.avatar:
            profile.avatar.delete(save=False)
            profile.avatar = None
            profile.save(update_fields=["avatar"])
            logger.info(f"Operator tomonidan avatar o'chirildi: {profile.user.phone_number}")

        return Response(status=status.HTTP_204_NO_CONTENT)


# ================================
# 3) Detal ko‘rish/yangilash/o‘chirish
# ================================
class PatientDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/DELETE: Operator — faqat o'zi yaratgan; Admin — barcha.
    """
    serializer_class = PatientProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrOperator]

    def get_queryset(self):
        if _is_swagger(self) or not self.request.user.is_authenticated:
            return PatientProfile.objects.none()

        user = self.request.user
        role = _norm_role(user)

        base = (PatientProfile.objects
                .select_related('user', 'created_by', 'stage', 'tag')
                .prefetch_related('documents', 'history', 'messages'))

        if role == 'operator':
            return base.filter(created_by=user)
        return base  # admin, doctor, superadmin

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = PatientProfileCreateUpdateSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(PatientProfileSerializer(instance, context={"request": request}).data)


# ================================
# 4) Bosqichni o‘zgartirish
# ================================
class ChangeStageView(APIView):
    """
    PATCH /api/patients/<id>/change-stage/
    {"new_stage_id": 1, "comment": "..." }
    """
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrOperator]

    def patch(self, request, patient_id):
        patient = get_object_or_404(PatientProfile, id=patient_id)
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
            patient_profile=patient,
            author=request.user,
            comment=comment
        )

        logger.info(f"Bosqich o'zgartirildi: {patient.full_name} ({old_stage} → {new_stage})")
        return Response({"success": True}, status=status.HTTP_200_OK)


# ================================
# 5) Hujjat yuklash
# ================================
class PatientDocumentCreateView(generics.CreateAPIView):
    """
    POST /api/patients/<patient_id>/documents/
    """
    queryset = PatientDocument.objects.all()
    serializer_class = PatientDocumentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrOperator]

    def perform_create(self, serializer):
        patient_profile = get_object_or_404(PatientProfile, id=self.kwargs['patient_id'])
        self.check_object_permissions(self.request, patient_profile)

        source_type = _norm_role(self.request.user)
        if source_type == 'patient':
            source = 'patient'
        elif source_type == 'operator':
            source = 'operator'
        elif source_type == 'partner':
            source = 'partner'
        else:
            source = 'other'

        serializer.save(
            patient_profile=patient_profile,
            uploaded_by=self.request.user,
            source_type=source
        )


# ================================
# 6) Hujjatni o‘chirish
# ================================
class PatientDocumentDeleteView(generics.DestroyAPIView):
    """
    DELETE /api/documents/<id>/
    """
    queryset = PatientDocument.objects.all()
    serializer_class = PatientDocumentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrOperator]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.check_object_permissions(request, instance)

        role = _norm_role(request.user)
        if role == 'operator' and instance.uploaded_by != request.user:
            raise PermissionDenied("Siz faqat o'zingiz yuklagan hujjatlarni o'chira olasiz.")

        filename = instance.file.name if instance.file else "unknown"
        self.perform_destroy(instance)

        logger.info(f"Hujjat o'chirildi: {filename} by {request.user}")
        return Response(status=status.HTTP_204_NO_CONTENT)


# ================================
# 7) Javob xatlari
# ================================
class ResponseLettersListView(generics.ListAPIView):
    """
    GET /api/response-letters/ — faqat response_letters bosqichidagi bemorlar
    """
    serializer_class = PatientProfileWithDocumentsSerializer
    permission_classes = [permissions.IsAuthenticated, IsOperatorOrHigher]

    def get_queryset(self):
        if _is_swagger(self) or not self.request.user.is_authenticated:
            return PatientProfile.objects.none()

        return (PatientProfile.objects
                .filter(stage__code_name='response_letters')
                .select_related('user', 'created_by', 'stage', 'tag')
                .prefetch_related('documents'))


# ================================
# 8-9) Teglar
# ================================
class TagListView(generics.ListCreateAPIView):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated, IsOperatorOrHigher]


class TagDeleteView(generics.DestroyAPIView):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated, IsOperatorOrHigher]


# ================================
# 10) Bosqichlar
# ================================
class StageListView(generics.ListAPIView):
    queryset = Stage.objects.order_by('order')
    serializer_class = StageSerializer
    permission_classes = [permissions.IsAuthenticated, IsOperatorOrHigher]


# ================================
# 11) Shartnoma tasdiqlash
# ================================
class ContractApproveView(APIView):
    """
    POST /api/contracts/<id>/approve/
    """
    permission_classes = [permissions.IsAuthenticated, IsContractOwnerOrAdmin]

    def post(self, request, contract_id):
        contract = get_object_or_404(Contract.objects.select_related('patient_profile'), id=contract_id)
        self.check_object_permissions(request, contract)

        if contract.status == 'approved':
            return Response({"error": "Shartnoma allaqachon tasdiqlangan."}, status=status.HTTP_400_BAD_REQUEST)

        contract.status = 'approved'
        contract.approved_by = request.user
        contract.approved_at = timezone.now()
        contract.save(update_fields=['status', 'approved_by', 'approved_at'])

        logger.info(f"Shartnoma tasdiqlandi: {contract.id} by {request.user}")
        return Response({"message": "Shartnoma muvaffaqiyatli tasdiqlandi"}, status=status.HTTP_200_OK)
