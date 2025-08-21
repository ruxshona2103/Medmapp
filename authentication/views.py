from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets, filters, generics, permissions
from rest_framework.permissions import AllowAny, IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework_simplejwt.tokens import RefreshToken
from authentication.models import CustomUser, MedicalFile, PendingUser
from .serializers import (
    RegisterSerializer,
    OtpRequestSerializer,
    OtpVerifySerializer,
    UserSerializer,
    LoginSerializer,
    MedicalFileSerializer,
)

User = get_user_model()


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=RegisterSerializer)
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pending_user = serializer.save()

        return Response(
            {
                "message": "Ro'yxatdan o'tish muvaffaqiyatli yakunlandi! Endi OTP so‘rashingiz mumkin.",
                "phone_number": pending_user.phone_number,
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
        return Response(data, status=status.HTTP_200_OK)


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

        # token yaratish
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

    @swagger_auto_schema(request_body=LoginSerializer,
                         responses={200: "Login successful, returns tokens"})
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": UserSerializer(user).data
        }, status=status.HTTP_200_OK)


class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['role', 'is_active']
    search_fields = ['phone_number', 'first_name', 'last_name']
    ordering_fields = ['date_joined']


class MedicalFileUploadView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Fayl yuklash",
        request_body=MedicalFileSerializer
    )
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
