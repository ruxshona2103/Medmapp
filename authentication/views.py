# authentication/views.py
from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from drf_yasg import openapi
from rest_framework import status, viewsets, filters, generics, permissions
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
)

# 👉 OTP tasdiqlanganda avtomatik Patient yaratish uchun
from patients.models import Patient, PatientHistory
from patients.utils import get_default_stage

User = get_user_model()


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Ro‘yxatdan o‘tish (pending user yaratiladi).",
        request_body=RegisterSerializer
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
        operation_description="Ko‘rsatilgan telefon raqamiga OTP jo‘natish.",
        request_body=OtpRequestSerializer
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
        operation_description=(
            "OTP ni tasdiqlaydi. Muvaffaqiyatda JWT tokenlarni qaytaradi. "
            "Foydalanuvchi roli 'patient' bo‘lsa (yoki rol yo‘q bo‘lsa), Patient avtomatik yaratiladi "
            "va birlamchi bosqich (Yangi) hamda default tag biriktiriladi."
        ),
        request_body=OtpVerifySerializer,
        responses={200: "OTP tasdiqlandi va token qaytarildi"},
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
        operation_description="Login (telefon raqam/parol yoki berilgan credential) va JWT tokenlar qaytarish.",
        request_body=LoginSerializer,
        responses={200: "Kirish muvaffaqiyatli, JWT tokenlar qaytariladi"},
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
        operation_description="Foydalanuvchiga tibbiy fayl yuklash.",
        request_body=MedicalFileSerializer,
        responses={201: "Fayl yuklandi"},
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


class OperatorTokenRefreshView(TokenRefreshView):
    """
    Refresh token orqali yangi access token olish.
    """
    pass


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
        operation_summary="🔐 Partner Login",
        operation_description="""
        Hamkor uchun login endpoint.

        Credentials:
        - phone_number: +998XXXXXXXXX
        - password: partner paroli

        Returns:
        - access: Access token (15 daqiqa)
        - refresh: Refresh token (1 kun)
        - user: Partner ma'lumotlari
        """,
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['phone_number', 'password'],
            properties={
                'phone_number': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Telefon raqam',
                    example='+998999999996'
                ),
                'password': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Parol',
                    example='partner123'
                ),
            },
        ),
        responses={
            200: openapi.Response(
                description='Login muvaffaqiyatli',
                examples={
                    'application/json': {
                        'access': 'eyJ0eXAiOiJKV1QiLCJhbGc...',
                        'refresh': 'eyJ0eXAiOiJKV1QiLCJhbGc...',
                        'user': {
                            'id': 5,
                            'phone_number': '+998999999996',
                            'role': 'partner',
                            'first_name': 'Test',
                            'last_name': 'Partner',
                            'partner_id': 1,
                            'partner_name': 'Test Klinika',
                            'partner_code': 'TEST_001'
                        }
                    }
                }
            ),
            401: 'Noto\'g\'ri credentials yoki role',
        },
        tags=['auth']  # ← BITTA TAG!
    )
    def post(self, request, *args, **kwargs):
        """Partner login"""
        return super().post(request, *args, **kwargs)


class PartnerTokenRefreshView(TokenRefreshView):
    @swagger_auto_schema(
        operation_summary="🔄 Partner Token Refresh",
        operation_description="Refresh token orqali yangi access token olish",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['refresh'],
            properties={
                'refresh': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Refresh token'
                ),
            }
        ),
        responses={
            200: openapi.Response(
                'Success',
                openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'access': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            )
        },
        tags=['auth']
    )
    def post(self, request, *args, **kwargs):
        """Token refresh"""
        return super().post(request, *args, **kwargs)
