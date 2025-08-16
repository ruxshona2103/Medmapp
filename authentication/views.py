from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from drf_yasg.utils import swagger_auto_schema
from .serializers import OtpRequestSerializer, OtpVerifySerializer


class OtpRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(request_body=OtpRequestSerializer)
    def post(self, request):
        serializer = OtpRequestSerializer(data=request.data)
        if serializer.is_valid():
            # Bu joyda serializer.save() random OTP yaratishi mumkin
            # Swagger testi uchun biz OTP ni har safar 123456 qilamiz
            serializer.save(otp="123456")
            return Response({"message": "OTP yuborildi", "otp": "123456"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OtpVerifyView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(request_body=OtpVerifySerializer)
    def post(self, request):
        serializer = OtpVerifySerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            tokens = serializer.create_token(user)
            return Response(tokens, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
