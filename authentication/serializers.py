from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import serializers
from authentication.models import CustomUser, MedicalFile, PendingUser
from config import settings
from django.utils import timezone
from datetime import timedelta
from .otp_service import OtpService
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'first_name', 'last_name', 'phone_number', 'district', 'role', 'is_active', 'date_joined']
        ref_name = "AuthUserSerializer"  # <<<<<<< MUHIM: ref_name farqi



class RegisterSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField()

    class Meta:
        model = PendingUser
        fields = ['phone_number', 'first_name', 'last_name', 'district']

    def validate_phone_number(self, value):
        if not value.startswith("+998"):
            raise serializers.ValidationError("Telefon raqam +998 bilan boshlanishi kerak")
        if CustomUser.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("Bu raqam bilan ro'yxatdan o'tilgan")
        return value

    def create(self, validated_data):
        phone = validated_data['phone_number']
        pending_user, _ = PendingUser.objects.update_or_create(
            phone_number=phone,
            defaults={
                "first_name": validated_data.get("first_name", ""),
                "last_name": validated_data.get("last_name", ""),
                "district": validated_data.get("district", ""),
                "role": "user",
                "expires_at": timezone.now() + timedelta(minutes=5),
            }
        )
        return pending_user

class OtpRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField()

    def validate_phone_number(self, value):
        if not value.startswith("+998"):
            raise serializers.ValidationError("Telefon raqam +998 bilan boshlanishi kerak.")
        if not (PendingUser.objects.filter(phone_number=value).exists()
                or CustomUser.objects.filter(phone_number=value).exists()):
            raise serializers.ValidationError("Avval ro‘yxatdan o‘ting.")
        return value

    def create(self, validated_data):
        phone = validated_data["phone_number"]
        otp_code = OtpService.send_otp(phone)
        cache.set(f"otp_{phone}", otp_code, timeout=300)  # 5 daqiqa

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

        if not cached_code:
            raise serializers.ValidationError("OTP yuborilmagan yoki muddati tugagan.")
        if cached_code != code:
            raise serializers.ValidationError("Noto‘g‘ri kod.")

        try:
            pending = PendingUser.objects.get(phone_number=phone)
        except PendingUser.DoesNotExist:
            if not CustomUser.objects.filter(phone_number=phone).exists():
                raise serializers.ValidationError("Bunday raqam uchun ro‘yxatdan o‘tish topilmadi.")

        attrs["pending_user"] = pending if 'pending' in locals() else None
        return attrs


    def create(self, validated_data):
        pending = validated_data.get("pending_user")
        phone = pending.phone_number if pending else validated_data.get("phone_number")

        user, created = CustomUser.objects.get_or_create(
            phone_number=phone,
            defaults={
                "first_name": (pending.first_name if pending else ""),
                "last_name": (pending.last_name if pending else ""),
                "district": (pending.district if pending else ""),
                "role": (pending.role if pending else "user"),
                "is_active": True,
            }
        )
        return user


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


# ----------------------------------------------------------------------------------------------------------------------


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Telefon + parol orqali JWT olish.
    Token ichiga role, phone_number va full_name qo‘shamiz.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Qo‘shimcha claimlar
        token['role'] = user.role
        token['phone_number'] = user.phone_number
        token['full_name'] = user.get_full_name()
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        # User haqida qo‘shimcha info response’da qaytsin
        data['user'] = {
            "id": self.user.id,
            "phone_number": self.user.phone_number,
            "role": self.user.role,
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
        }
        return data


class OperatorLoginSerializer(TokenObtainPairSerializer):
    """
    Faqat operator foydalanuvchilarga JWT token beradi.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['phone_number'] = user.phone_number
        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        # faqat operator login qila oladi
        if getattr(self.user, "role", None) != "operator":
            raise AuthenticationFailed("Faqat operator login qila oladi.")

        # user haqida qo'shimcha info qaytarib beramiz
        data['user'] = {
            "id": self.user.id,
            "phone_number": self.user.phone_number,
            "role": self.user.role,
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
        }
        return data