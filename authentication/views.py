from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets, filters, generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from django.utils import timezone
from datetime import timedelta
from authentication.models import CustomUser, MedicalFile, OTP, PendingUser
from .serializers import (
    RegisterSerializer,
    OtpRequestSerializer,
    OtpVerifySerializer,
    LoginSerializer,
    UserSerializer,
    MedicalFileSerializer,
    LogoutSerializer, MyTokenObtainPairSerializer
)
from .otp_service import OtpService


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=RegisterSerializer)
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        phone = validated_data["phone_number"]
        pending_user, created = PendingUser.objects.update_or_create(
            phone_number=phone,
            defaults={
                "first_name": validated_data.get("first_name", ""),
                "last_name": validated_data.get("last_name", ""),
                "district": validated_data.get("district", ""),
                "role": "user",
                "expires_at": timezone.now() + timedelta(minutes=5)
            }
        )

        otp_code = OtpService.send_otp(phone, dev_mode=True)
        return Response(
            {
                "message": "**Ro‘yxatdan o‘tish muvaffaqiyatli!** Telefon raqamingizni tasdiqlash uchun OTP yuborildi.",
                "phone_number": phone,
                "otp": otp_code if True else "****"
            },
            status=status.HTTP_201_CREATED
        )


class OtpRequestView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=OtpRequestSerializer)
    def post(self, request):
        serializer = OtpRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.save()
        return Response(
            data,
            status=status.HTTP_200_OK
        )


class OtpVerifyView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=OtpVerifySerializer,
        responses={200: "OTP tasdiqlandi va token qaytarildi"}
    )
    def post(self, request):
        serializer = OtpVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)

        return Response(
            {
                "message": "**Telefon raqam tasdiqlandi!**",
                "user": UserSerializer(user).data,
                "access": access,
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=LoginSerializer)
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.save()
        return Response(data, status=status.HTTP_200_OK)
# -------------------- LOGOUT VIEW --------------------

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=LogoutSerializer)
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            refresh_token = serializer.validated_data['refresh']
            token = RefreshToken(refresh_token)
            token.blacklist()  # endi ishlaydi
            return Response({"message": "Token blacklist qilindi, logout muvaffaqiyatli"}, status=status.HTTP_200_OK)
        except TokenError:
            return Response({"error": "Token noto‘g‘ri yoki muddati tugagan"}, status=status.HTTP_400_BAD_REQUEST)

class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['role', 'is_active']
    search_fields = ['phone_number', 'first_name', 'last_name']
    ordering_fields = ['date_joined']


class MedicalFileUploadView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(operation_description="Fayl yuklash", request_body=MedicalFileSerializer)
    def post(self, request, pk=None):
        serializer = MedicalFileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user_id=pk)
        return Response({'message': 'Fayl yuklandi'}, status=status.HTTP_201_CREATED)


class MedicalFileListView(generics.ListAPIView):
    serializer_class = MedicalFileSerializer

    def get_queryset(self):
        user_id = self.kwargs['pk']
        return MedicalFile.objects.filter(user_id=user_id)

