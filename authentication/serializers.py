from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from authentication.models import CustomUser, MedicalFile, OTP, PendingUser
from config import settings
from .otp_service import OtpService
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'first_name', 'last_name', 'phone_number', 'district', 'role', 'is_active', 'date_joined']


class RegisterSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField()

    class Meta:
        model = PendingUser
        fields = ['phone_number', 'first_name', 'last_name', 'district']

    def validate_phone_number(self, value):
        if not value.startswith("+998"):
            raise serializers.ValidationError("Telefon raqam +998 bilan boshlanishi kerak.")
        return value

    def create(self, validated_data):
        phone = validated_data['phone_number']
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
        return pending_user

class OtpRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField()

    def validate_phone_number(self, value):
        if not value.startswith("+998"):
            raise serializers.ValidationError("Telefon raqam +998 bilan boshlanishi kerak.")
        return value

    def create(self, validated_data):
        phone = validated_data["phone_number"]
        expires_at = timezone.now() + timedelta(minutes=5)
        pending_user, created = PendingUser.objects.get_or_create(
            phone_number=phone,
            defaults={
                "first_name": "",
                "last_name": "",
                "district": "",
                "role": "user",
                "expires_at": expires_at
            }
        )
        otp_code = OtpService.send_otp(phone, dev_mode=settings.DEBUG)
        cache.set(f"otp_{phone}", otp_code, timeout=300)

        return {
            "message": "OTP muvaffaqiyatli yuborildi!",
            "phone_number": phone,
            "otp": otp_code if settings.DEBUG else "****"
        }


class OtpVerifySerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    code = serializers.CharField()

    def validate(self, attrs):
        phone = attrs.get("phone_number")
        code = attrs.get("code")
        cached_code = cache.get(f"otp_{phone}")
        if cached_code != code:
            raise serializers.ValidationError("Noto‘g‘ri kod yoki telefon raqam.")
        try:
            pending_user = PendingUser.objects.get(phone_number=phone)
        except PendingUser.DoesNotExist:
            raise serializers.ValidationError("Noto‘g‘ri kod yoki telefon raqam.")
        if pending_user.expires_at < timezone.now():
            raise serializers.ValidationError("OTP muddati tugagan.")

        attrs["pending_user"] = pending_user
        return attrs

    def create(self, validated_data):
        pending_user = validated_data["pending_user"]

        # Agar hali User mavjud bo‘lmasa, yaratish
        user, created = CustomUser.objects.get_or_create(
            phone_number=pending_user.phone_number,
            defaults={
                "first_name": pending_user.first_name,
                "last_name": pending_user.last_name,
                "district": pending_user.district,
            }
        )
        return user

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    phone_number = serializers.CharField(required=True)

    def validate(self, attrs):
        phone = attrs.get("phone_number")
        password = attrs.get("password")

        try:
            user = CustomUser.objects.get(phone_number=phone)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("Bunday telefon raqam bilan user topilmadi")

        if not user.check_password(password):
            raise serializers.ValidationError("Parol noto‘g‘ri")

        refresh = self.get_token(user)

        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                "id": user.id,
                "phone_number": user.phone_number,
                "first_name": user.first_name,
                "last_name": user.last_name,
            }
        }


class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    code = serializers.CharField()

    def validate(self, attrs):
        phone = attrs.get("phone_number")
        code = attrs.get("code")
        cached_otp = cache.get(f"otp_{phone}")
        if not cached_otp:
            raise serializers.ValidationError({"detail": "OTP muddati tugagan yoki yuborilmagan."})

        if code != cached_otp:
            raise serializers.ValidationError({"detail": "Noto‘g‘ri kod."})

        try:
            user = User.objects.get(phone_number=phone)
        except User.DoesNotExist:
            raise serializers.ValidationError({"detail": "Bunday foydalanuvchi topilmadi, oldin ro‘yxatdan o‘ting."})

        attrs["user"] = user
        return attrs

class MedicalFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalFile
        fields = ['id', 'user', 'file', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at', 'user']