# authentication/views.py
from django.contrib.auth import get_user_model
from django.db import transaction

from rest_framework import status, viewsets, filters, generics, permissions
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg.utils import swagger_auto_schema
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from authentication.models import CustomUser, MedicalFile
from .serializers import (
    RegisterSerializer,
    OtpRequestSerializer,
    OtpVerifySerializer,
    UserSerializer,
    LoginSerializer,
    MedicalFileSerializer,
    OperatorLoginSerializer,
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


class OtpVerifyView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description=(
            "OTP ni tasdiqlaydi. Muvaffaqiyatda JWT tokenlarni qaytaradi. "
            "Foydalanuvchi roli 'patient' bo‘lsa (yoki rol yo‘q bo‘lsa), Patient avtomatik yaratiladi "
            "va birlamchi bosqich (Yangi) biriktiriladi."
        ),
        request_body=OtpVerifySerializer,
        responses={200: "OTP tasdiqlandi va token qaytarildi"},
    )
    def post(self, request):
        serializer = OtpVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # 👉 Patient avtomatik yaratilishi (safe qiymatlar bilan)
        with transaction.atomic():
            # Rol maydoni bo‘lsa va patient bo‘lmasa — patient qilib qo‘yamiz
            if hasattr(user, "role") and (user.role or "").lower() != "patient":
                user.role = "patient"
                user.save(update_fields=["role"])

            # Patient mavjud emasmi? — yaratamiz
            if not Patient.objects.filter(created_by=user, is_archived=False).exists():
                stage = get_default_stage()  # 'Yangi' / 'new' / birinchi bosqichdan biri

                # SAFE qiymatlar (None ketmasligi uchun)
                safe_full_name = (
                    f"{(user.first_name or '').strip()} {(user.last_name or '').strip()}".strip()
                    or (getattr(user, "username", "") or getattr(user, "phone_number", "") or "Foydalanuvchi")
                )
                safe_phone = (getattr(user, "phone_number", "") or "").strip()
                safe_email = (getattr(user, "email", "") or "").strip()   # <<< NULL o‘rniga bo‘sh string

                patient = Patient.objects.create(
                    created_by=user,
                    full_name=safe_full_name,
                    phone_number=safe_phone,
                    email=safe_email,     # <<< endi DBga NULL ketmaydi
                    stage=stage,
                )
                PatientHistory.objects.create(
                    patient=patient,
                    author=user,
                    comment="Bemor profili yaratildi",
                )

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
