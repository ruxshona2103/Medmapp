# views.py (updated)

from django.utils import timezone
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
from applications.models import Application

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
            logger.info(
                "Swagger yoki autentifikatsiya qilinmagan foydalanuvchi uchun bo'sh queryset"
            )
            return Patient.objects.none()

        user = self.request.user
        role = _norm_role(user)
        logger.info(f"User: {user.phone_number}, Role: {role}")

        base = Patient.objects.select_related(
            "stage", "tag", "profile__user", "created_by"
        ).prefetch_related("documents", "history")
        logger.info(f"Base queryset count: {base.count()}")

        # Agar "patient" roli bo'lsa, faqat o'ziga tegishli Patientni ko'radi
        if role == "patient":
            queryset = base.filter(profile__user=user)
            logger.info(f"Patient queryset count: {queryset.count()}")
            return queryset

        # Superadmin yoki operator uchun barcha Patientlarni qaytarish
        if role in ["superadmin", "operator"]:
            # Applicationlardan Patient yozuvlarini avtomatik yaratish
            self.create_missing_patients_from_applications()
            return base.all()

        # Boshqa rollar uchun filtrlangan queryset
        one_day_ago = timezone.now() - timezone.timedelta(days=1)
        queryset = base.filter(created_at__lte=one_day_ago)
        logger.info(f"Filtered queryset count (1 kundan eski): {queryset.count()}")
        return queryset

    def create_missing_patients_from_applications(self):
        """
        Mavjud Applicationlarni tekshirib, agar ularga mos Patient yozuvi yo'q bo'lsa,
        avtomatik yaratish. Agar mavjud bo'lsa, hech qanday xabar yubormaslik.
        """
        # Applicationlarda patient_id orqali bog'langan userlarni olish
        applications = Application.objects.select_related("patient").all()
        created_count = 0

        for app in applications:
            user = app.patient
            logger.info(
                f"Application {app.application_id} uchun Patient tekshirilmoqda, User: {user.phone_number}"
            )

            # PatientProfile mavjudligini tekshirish
            try:
                profile = PatientProfile.objects.get(user=user)
            except PatientProfile.DoesNotExist:
                full_name = user.get_full_name() or user.phone_number or "Noma'lum"
                profile = PatientProfile.objects.create(
                    user=user,
                    full_name=full_name,
                    gender="male",
                    complaints=app.complaint or "",
                    previous_diagnosis=app.diagnosis or "",
                )
                logger.info(
                    f"Yangi PatientProfile yaratildi: {profile.id} for Application {app.application_id}"
                )

            # Patient yozuvini tekshirish va yaratish
            patient_exists = Patient.objects.filter(profile=profile).exists()
            if not patient_exists:
                patient = Patient.objects.create(
                    profile=profile,
                    full_name=profile.full_name,
                    phone=user.phone_number,
                    email=user.email if hasattr(user, "email") else None,
                    created_by=user,
                    source="Application",
                    created_at=timezone.now(),
                )
                created_count += 1
                logger.info(
                    f"Yangi Patient yaratildi: {patient.id} for Application {app.application_id}"
                )
            else:
                logger.info(
                    f"Mavjud Patient ishlatildi for Application {app.application_id}"
                )

        if created_count > 0:
            logger.info(
                f"{created_count} ta Application uchun Patient yozuvlari avtomatik yaratildi"
            )
        else:
            logger.info("Hech qanday yangi Patient yaratilmadi, chunki barchasi mavjud")


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
# views.py
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

    def patch(self, request):
        if _is_swagger(self):
            return Response({})

        user = request.user
        if _norm_role(user) != "patient":
            raise PermissionDenied("Faqat bemorlar uchun.")

        profile = get_object_or_404(PatientProfile, user=user)

        # Serializer yordamida ma'lumotlarni yangilash
        serializer = PatientProfileSerializer(
            profile, data=request.data, partial=True, context={"request": request}
        )

        serializer.is_valid(raise_exception=True)
        updated_instance = serializer.save()

        # Patient ma'lumotlarini yangilash
        if hasattr(updated_instance, "patient_record"):
            patient = updated_instance.patient_record
            if "full_name" in request.data:
                patient.full_name = request.data.get("full_name", patient.full_name)
            if "email" in request.data:
                patient.email = request.data.get("email", patient.email)
            if "region" in request.data:
                patient.region = request.data.get("region", patient.region)
            patient.save(update_fields=["full_name", "email", "region"])

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


# ==========================================
# 11) Bemor profilingini o'chirish (foydalanuvchi hisobini o'chirish)
# ==========================================
class PatientDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        user = request.user
        if _norm_role(user) != "patient":
            raise PermissionDenied("Faqat bemorlar o'z profilini o'chira oladi.")

        # Foydalanuvchini o'chirish (profile va patient kaskad orqali o'chiriladi)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
