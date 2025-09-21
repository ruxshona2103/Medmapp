# views.py

import logging
from django.shortcuts import get_object_or_404
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, NotFound
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Patient, PatientProfile, Stage, Tag, PatientHistory, PatientDocument
from .serializers import (
    PatientSerializer,
    PatientProfileSerializer,
    StageSerializer,
    TagSerializer,
    PatientDocumentSerializer,
    UserSerializer,
    PatientAvatarSerializer,
)

User = get_user_model()
logger = logging.getLogger(__name__)


# ==========================================
# Helper funksiyalar
# ==========================================
def _is_swagger(view) -> bool:
    """Swagger schema generatsiya paytida queryset ishlamasligi uchun."""
    return getattr(view, "swagger_fake_view", False)


def _norm_role(user):
    """User rolini normalize qilish: 'user' -> 'patient'."""
    if not hasattr(user, "role"):
        return "anonymous"
    role = getattr(user, "role", "").lower()
    return "patient" if role == "user" else role


# ==========================================
# 1) Barcha PatientProfile lar ro‘yxati
# ==========================================
class PatientProfileListView(generics.ListAPIView):
    serializer_class = PatientProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]

    def get_queryset(self):
        if _is_swagger(self) or not self.request.user.is_authenticated:
            return PatientProfile.objects.none()

        user = self.request.user
        role = _norm_role(user)

        base = PatientProfile.objects.select_related("user").prefetch_related(
            "patient_record__documents", "patient_record__history"
        )

        return base.filter(user=user) if role == "patient" else base


# ==========================================
# 2) Barcha Patient lar ro‘yxati
# ==========================================
class PatientListView(generics.ListAPIView):
    serializer_class = PatientSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["stage", "tag", "created_by"]

    def get_queryset(self):
        if _is_swagger(self) or not self.request.user.is_authenticated:
            return Patient.objects.none()

        user = self.request.user
        role = _norm_role(user)

        base = Patient.objects.select_related(
            "stage", "tag", "profile__user", "created_by"
        ).prefetch_related("documents", "history")

        # Agar "patient" roli bo'lsa, faqat o'ziga tegishli Patientni ko'radi
        if role == "patient":
            return base.filter(profile__user=user)

        # Faqat superadmin yangi yaratilgan Patientlarni ko'radi
        # Boshqa rollar (operator, admin) faqat avvaldan mavjud bo'lganlarni ko'radi
        if role == "superadmin":
            return (
                base.all()
            )  # Superadmin hamma narsani ko'radi, shu jumladan yangi ro'yxatdan o'tganlarni
        else:
            # Operator va admin faqat avvaldan mavjud bo'lgan Patientlarni ko'radi
            # Yangi yaratilganlarni (signal orqali avto-yaratilganlarni) cheklaymiz
            # Bu yerda "created_at" yoki boshqa belgi orqali filtrlash mumkin
            # Masalan, faqat 1 kundan oldingi rekordlarni ko'rish
            from django.utils import timezone

            one_day_ago = timezone.now() - timezone.timedelta(days=1)
            return base.filter(created_at__lte=one_day_ago)


# ==========================================
# 3) Yangi Patient yaratish
# ==========================================
class PatientCreateView(generics.CreateAPIView):
    serializer_class = PatientSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        role = _norm_role(user)

        patient = serializer.save(created_by=user)

        if role == "patient":
            try:
                profile = user.patient_profile
                patient.profile = profile
                patient.full_name = user.get_full_name() or user.phone_number
                patient.phone = user.phone_number
                patient.email = self.request.data.get("email")  # ✅ tuzatildi
                patient.save()
            except PatientProfile.DoesNotExist:
                raise NotFound("Sizda bemor profili mavjud emas.")

        PatientHistory.objects.create(
            patient=patient, author=user, comment="Bemor jarayoni tizimga qo'shildi"
        )
        logger.info(f"Bemor jarayoni yaratildi: {patient.full_name}")


# ==========================================
# 4) Bemor o‘z profilingini ko‘rish va O'ZGARTIRISH
# ==========================================
class PatientMeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if _is_swagger(self):
            return Response({})

        user = request.user
        if _norm_role(user) != "patient":
            raise PermissionDenied("Faqat bemorlar uchun.")

        profile = get_object_or_404(
            PatientProfile.objects.select_related("user").prefetch_related(
                "patient_record__documents", "patient_record__history"
            ),
            user=user,
        )
        serializer = PatientProfileSerializer(profile, context={"request": request})
        return Response(serializer.data)

    # QO'SHILDI: Bemor o'z profilini qisman (PATCH) yangilashi uchun
    def patch(self, request):
        if _is_swagger(self):
            return Response({})

        user = request.user
        if _norm_role(user) != "patient":
            raise PermissionDenied("Faqat bemorlar uchun.")

        profile = get_object_or_404(PatientProfile, user=user)

        # Serializer yordamida ma'lumotlarni yangilaymiz
        # partial=True faqat yuborilgan maydonlarni yangilashni bildiradi
        serializer = PatientProfileSerializer(
            profile, data=request.data, partial=True, context={"request": request}
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Yangilangan ma'lumotlarni qaytaramiz
        return Response(serializer.data)


# ==========================================
# 5) Operator o‘z profilingini ko‘rish
# ==========================================
class OperatorMeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if _is_swagger(self):
            return Response({})

        user = request.user
        if _norm_role(user) != "operator":
            raise PermissionDenied("Faqat operatorlar uchun.")

        return Response(UserSerializer(user, context={"request": request}).data)


# ==========================================
# 6) Bemor bosqichini o‘zgartirish
# ==========================================
class ChangeStageView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, patient_id):
        if _is_swagger(self):
            return Response({})

        patient = get_object_or_404(Patient, id=patient_id)
        user = request.user

        if _norm_role(user) == "patient":
            raise PermissionDenied("Bemorlar bosqichni o‘zgartira olmaydi.")

        new_stage_id = request.data.get("new_stage_id")
        if not new_stage_id:
            return Response(
                {"error": "'new_stage_id' majburiy."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_stage = get_object_or_404(Stage, id=new_stage_id)

        old_stage = patient.stage
        patient.stage = new_stage
        patient.save(update_fields=["stage"])

        comment = request.data.get(
            "comment",
            f"Bosqich o‘zgartirildi: {getattr(old_stage, 'title', '—')} → {new_stage.title}",
        )
        PatientHistory.objects.create(patient=patient, author=user, comment=comment)

        return Response(
            {"success": True, "new_stage": new_stage.title}, status=status.HTTP_200_OK
        )


# ==========================================
# 7) Hujjat yuklash
# ==========================================
class PatientDocumentCreateView(generics.CreateAPIView):
    serializer_class = PatientDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        patient_id = self.kwargs.get("patient_id")
        patient = get_object_or_404(Patient, id=patient_id)
        user = self.request.user
        role = _norm_role(user)

        if role == "patient" and patient.profile.user != user:
            raise PermissionDenied("Siz faqat o‘zingiz uchun hujjat yuklay olasiz.")

        source_type = role if role in ["operator", "patient", "partner"] else "operator"

        serializer.save(patient=patient, uploaded_by=user, source_type=source_type)


# ==========================================
# 8) Hujjatni o‘chirish
# ==========================================
class PatientDocumentDeleteView(generics.DestroyAPIView):
    serializer_class = PatientDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if _is_swagger(self):
            return PatientDocument.objects.none()
        return PatientDocument.objects.all()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        user = request.user
        role = _norm_role(user)

        if role == "patient" and instance.patient.profile.user != user:
            raise PermissionDenied(
                "Siz faqat o‘zingiz yuklagan hujjatlarni o‘chira olasiz."
            )
        if role == "operator" and instance.uploaded_by != user:
            raise PermissionDenied(
                "Siz faqat o‘zingiz yuklagan hujjatlarni o‘chira olasiz."
            )

        filename = instance.file.name if instance.file else "unknown"
        self.perform_destroy(instance)
        logger.info(f"Hujjat o‘chirildi: {filename}")
        return Response(status=status.HTTP_204_NO_CONTENT)


class PatientAvatarUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_patient_object(self, user):
        """
        Helper metod: Foydalanuvchi bo'yicha Patient obyektini topadi.
        AGAR MAVJUD BO'LMASA, YANGI PATIENT YARATADI.
        """
        if _norm_role(user) != "patient":
            raise PermissionDenied("Faqat bemorlar uchun.")

        profile = get_object_or_404(PatientProfile, user=user)

        patient = getattr(profile, "patient_record", None)

        if not patient:
            # O'ZGARTIRILDI: 'email=user.email,' qatori olib tashlandi
            patient = Patient.objects.create(
                profile=profile,
                full_name=user.get_full_name() or user.phone_number,
                phone=user.phone_number,
                created_by=user,
            )

        return patient

    # ... (patch va delete metodlari o'zgarishsiz qoladi) ...
    def patch(self, request, *args, **kwargs):
        """Yangi avatarni yuklash."""
        user = request.user
        patient = self.get_patient_object(user)

        serializer = PatientAvatarSerializer(
            instance=patient, data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        response_serializer = PatientProfileSerializer(
            patient.profile, context={"request": request}
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        """Mavjud avatarni o'chirish."""
        user = request.user
        patient = self.get_patient_object(user)

        if patient.avatar:
            patient.avatar.delete(save=True)

        return Response(status=status.HTTP_204_NO_CONTENT)


# ==========================================
# 9) Bosqichlar (CRUD)
# ==========================================
class StageListView(generics.ListCreateAPIView):
    queryset = Stage.objects.order_by("order")
    serializer_class = StageSerializer
    permission_classes = [permissions.IsAuthenticated]


# ==========================================
# 10) Teglar (CRUD)
# ==========================================
class TagListView(generics.ListCreateAPIView):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated]


class TagDeleteView(generics.DestroyAPIView):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated]

    def destroy(self, request, *args, **kwargs):
        if _norm_role(request.user) not in ["admin", "operator"]:
            raise PermissionDenied("Faqat admin yoki operator tegni o‘chira oladi.")
        return super().destroy(request, *args, **kwargs)
