from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics, status, viewsets, filters, permissions
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from authentication.models import CustomUser, MedicalFile
from .serializers import (
    RegisterSerializer, LoginSerializer,
    UserSerializer, MedicalFileSerializer
)
from rest_framework_simplejwt.tokens import RefreshToken
from django_filters.rest_framework import DjangoFilterBackend


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    @swagger_auto_schema(
        request_body=RegisterSerializer,
        responses={
            200: openapi.Response(
                description="Successful Registration",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'user': openapi.Schema(type=openapi.TYPE_OBJECT),
                        'access': openapi.Schema(type=openapi.TYPE_STRING),
                        'refresh': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: "Bad Request"
        }
    )

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserSerializer(user).data,
                'access': str(refresh.access_token),
                'refresh': str(refresh)
            })
        return Response(serializer.errors, status=400)

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    @swagger_auto_schema(
        request_body=LoginSerializer,
        responses={200: openapi.Response('Login successful', UserSerializer)},
        operation_description="Login user and return access & refresh token"
    )

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            return Response(serializer.validated_data)
        return Response(serializer.errors, status=400)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'refresh': openapi.Schema(type=openapi.TYPE_STRING, description='Refresh token to blacklist')
            },
            required=['refresh']
        ),
        responses={204: 'Successfully logged out', 400: 'Invalid token'},
        operation_description="Blacklist a refresh token to logout user"
    )

    def post(self, request):
        try:
            token = RefreshToken(request.data['refresh'])
            token.blacklist()
            return Response(status=204)
        except:
            return Response(status=400)

class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['role', 'is_active']
    search_fields = ['phone_number', 'full_name']
    ordering_fields = ['date_joined']


class MedicalFileUploadView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(operation_description="Fayl yuklash", request_body=MedicalFileSerializer)
    def post(self, request):
        if getattr(self, 'swagger_fake_view', False):
            return Response()  # <-- Swagger uchun faqat "mock" response

        serializer = MedicalFileSerializer(data=request.data)
        if serializer.is_valid():
            # Faylni saqlash logikasi shu yerda
            return Response({'message': 'Fayl yuklandi'})
        return Response(serializer.errors, status=400)


class MedicalFileListView(generics.ListAPIView):
    serializer_class = MedicalFileSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return MedicalFile.objects.none()
        user_id = self.kwargs['pk']
        return MedicalFile.objects.filter(user_id=user_id)
