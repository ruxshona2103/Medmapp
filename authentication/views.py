# authentication/views.py
from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from drf_yasg import openapi
from rest_framework import status, viewsets, filters, generics, permissions, parsers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg.utils import swagger_auto_schema
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from authentication.models import CustomUser, MedicalFile
from core.models import Stage, Tag
from .serializers import (
    RegisterSerializer,
    OtpRequestSerializer,
    OtpVerifySerializer,
    UserSerializer,
    LoginSerializer,
    MedicalFileSerializer,
    OperatorLoginSerializer, PartnerLoginSerializer,
    OperatorProfileSerializer,
)

# 👉 OTP tasdiqlanganda avtomatik Patient yaratish uchun
from patients.models import Patient, PatientHistory
from patients.utils import get_default_stage

User = get_user_model()


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="Ro'yxatdan o'tish",
        operation_description="Yangi foydalanuvchi yaratish (pending user)",
        request_body=RegisterSerializer,
        tags=["auth"]
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pending_user = serializer.save()
        return Response(
            {
                "message": "Ro'yxatdan o'tish muvaffaqiyatli yakunlandi! Endi OTP so‘rashingiz mumkin.",
                "phone_number": pending_user.phone_number,
            },
            status=status.HTTP_201_CREATED,
        )


class OtpRequestView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="OTP so'rash",
        operation_description="Telefon raqamiga OTP kod yuborish",
        request_body=OtpRequestSerializer,
        tags=["auth"]
    )
    def post(self, request):
        serializer = OtpRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.save()
        return Response(data, status=status.HTTP_200_OK)


def _ensure_default_stage() -> Stage:
    """
    Default bosqichni ishonchli qaytaradi:
    - avval get_default_stage() dan;
    - bo‘lmasa code_name='new';
    - bo‘lmasa order=1;
    - bo‘lmasa yaratib yuboradi.
    """
    # 1) util bo‘lsa
    try:
        st = get_default_stage()
        if st:
            return st
    except Exception:
        pass

    # 2) code_name='new'
    st = Stage.objects.filter(code_name="new").order_by("id").first()
    if st:
        return st

    # 3) order=1
    st = Stage.objects.order_by("order", "id").first()
    if st:
        return st

    # 4) hech narsa bo‘lmasa — minimal defaultni yaratamiz
    return Stage.objects.create(title="Yangi", color="#4F46E5", order=1, code_name="new")


def _ensure_default_tag() -> Tag | None:
    """
    Default tagni (‘Yangi’) qaytaradi yoki yaratadi.
    Agar Tag modelida qo‘shimcha majburiy maydonlar bo‘lsa,
    shu yerda mos default qiymat qo‘yiladi.
    """
    try:
        tag, _ = Tag.objects.get_or_create(name="Yangi", defaults={"color": "#4F46E5"})
        return tag
    except Exception:
        # Tag majburiy emas — xato bo‘lsa None qaytaramiz
        return None


class OtpVerifyView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="OTP tasdiqlash",
        operation_description="OTP kodni tekshirish va JWT token olish",
        request_body=OtpVerifySerializer,
        responses={200: "OTP tasdiqlandi va token qaytarildi"},
        tags=["auth"]
    )
    def post(self, request):
        serializer = OtpVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        try:
            with transaction.atomic():
                # Rolni patient qilib qo‘yish (bo‘lsa)
                if hasattr(user, "role") and (user.role or "").lower() != "patient":
                    user.role = "patient"
                    user.save(update_fields=["role"])

                # Patient bor-yo‘qligini tekshiramiz (idempotent)
                patient = (
                    Patient.objects.select_for_update()
                    .filter(created_by=user, is_archived=False)
                    .first()
                )

                if not patient:
                    stage = _ensure_default_stage()
                    tag = _ensure_default_tag()

                    # SAFE qiymatlar (None tushmasin)
                    safe_full_name = (
                        f"{(user.first_name or '').strip()} {(user.last_name or '').strip()}".strip()
                        or (getattr(user, "username", "") or getattr(user, "phone_number", "") or "Foydalanuvchi")
                    )
                    safe_phone = (getattr(user, "phone_number", "") or "").strip()
                    safe_email = (getattr(user, "email", "") or "").strip()

                    patient = Patient.objects.create(
                        user=user,
                        created_by=user,
                        full_name=safe_full_name,
                        phone_number=safe_phone,
                        email=safe_email,
                        stage=stage,
                        tag=tag,  # 🟢 default tag biriktirildi (agar mavjud bo‘lsa)
                    )
                    PatientHistory.objects.create(
                        patient=patient,
                        author=user,
                        comment="Bemor profili yaratildi",
                    )

        except IntegrityError:
            # Poygada parallel urinish bo‘lsa, yana bir bor chaqirib ko‘ramiz
            patient = Patient.objects.filter(created_by=user, is_archived=False).first()

        # JWT tokenlar
        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)

        return Response(
            {
                "message": "Telefon raqam tasdiqlandi!",
                "user": UserSerializer(user).data,
                "access": access,
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_summary="Login",
        operation_description="Telefon raqam va OTP kod bilan kirish",
        request_body=LoginSerializer,
        responses={200: "JWT tokenlar qaytarildi"},
        tags=["auth"]
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class UserViewSet(viewsets.ModelViewSet):
    """
    Foydalanuvchilar ro'yxati/CRUD (filter/search/ordering bilan).
    """
    permission_classes = [IsAuthenticated]
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["role", "is_active"]
    search_fields = ["phone_number", "first_name", "last_name"]
    ordering_fields = ["date_joined"]


class MedicalFileUploadView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Tibbiy fayl yuklash",
        operation_description="Foydalanuvchiga tibbiy fayl biriktirish",
        request_body=MedicalFileSerializer,
        responses={201: "Fayl yuklandi"},
        tags=["auth"]
    )
    def post(self, request, pk=None):
        serializer = MedicalFileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user_id=pk)
        return Response({"message": "Fayl yuklandi"}, status=status.HTTP_201_CREATED)


class MedicalFileListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MedicalFileSerializer

    def get_queryset(self):
        # Swagger schema generatsiyasida xatolik bermasligi uchun
        if getattr(self, "swagger_fake_view", False):
            return MedicalFile.objects.none()

        user_id = self.kwargs.get("pk")
        if not user_id:
            return MedicalFile.objects.none()
        return MedicalFile.objects.filter(user_id=user_id)


# ----------------- Operator JWT -----------------

class OperatorLoginView(TokenObtainPairView):
    """
    Operator login (phone_number + password) uchun JWT token olish.
    """
    serializer_class = OperatorLoginSerializer

    @swagger_auto_schema(operation_summary="Operator login", operation_description="Operator telefon va parol bilan kirish", tags=["operator"])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class OperatorTokenRefreshView(TokenRefreshView):
    """
    Refresh token orqali yangi access token olish.
    """

    @swagger_auto_schema(operation_summary="Operator token yangilash", operation_description="Refresh token bilan yangi access token olish", tags=["operator"])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class OperatorProfileView(generics.RetrieveUpdateAPIView):
    """
    Operator profili
    GET /api/auth/operator/profile/
    PUT /api/auth/operator/profile/
    PATCH /api/auth/operator/profile/
    """
    permission_classes = [IsAuthenticated]
    serializer_class = OperatorProfileSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_object(self):
        from authentication.models import OperatorProfile
        user = self.request.user
        user_role = getattr(user, 'role', None)
        if user_role != 'operator':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Faqat operatorlar kirishi mumkin.")
        profile, created = OperatorProfile.objects.get_or_create(
            user=user,
            defaults={
                'full_name': user.first_name or getattr(user, 'phone_number', '') or f'Operator_{user.id}',
                'employee_id': f'OP_{user.id}',
                'phone': getattr(user, 'phone_number', None),
            }
        )
        return profile

    @swagger_auto_schema(
        operation_summary="Operator profili",
        operation_description="Operator profil ma'lumotlarini olish",
        responses={200: OperatorProfileSerializer()},
        tags=["operator"]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Profilni to'liq yangilash (Avatar bilan)",
        operation_description="Operator profilini to'liq yangilash. Avatar yuklash mumkin (multipart/form-data).",
        request_body=OperatorProfileSerializer,
        responses={200: OperatorProfileSerializer()},
        tags=["operator"]
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Profilni qisman yangilash (Avatar bilan)",
        operation_description="Operator profilini qisman yangilash. Avatar yuklash mumkin (multipart/form-data).",
        request_body=OperatorProfileSerializer,
        responses={200: OperatorProfileSerializer()},
        tags=["operator"]
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


# ===============================================================
# PARTNER LOGIN
# ===============================================================
class PartnerLoginView(TokenObtainPairView):
    """
    Partner (Hamkor) login - JWT token olish
    """
    serializer_class = PartnerLoginSerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="Partner login",
        operation_description="Hamkor uchun telefon va parol bilan kirish",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['phone_number', 'password'],
            properties={
                'phone_number': openapi.Schema(type=openapi.TYPE_STRING, description='Telefon raqam'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, description='Parol'),
            },
        ),
        responses={200: "JWT tokenlar qaytarildi", 401: "Noto'g'ri credentials"},
        tags=['partner']
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class PartnerTokenRefreshView(TokenRefreshView):
    @swagger_auto_schema(
        operation_summary="Partner token yangilash",
        operation_description="Refresh token orqali yangi access token olish",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['refresh'],
            properties={
                'refresh': openapi.Schema(type=openapi.TYPE_STRING, description='Refresh token'),
            }
        ),
        responses={200: "Yangi access token"},
        tags=['partner']
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
