from django.core.cache import cache
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from authentication.models import CustomUser, MedicalFile, OTP, PendingUser
from config import settings
from .otp_service import OtpService
from django.utils import timezone
from datetime import timedelta


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'first_name', 'last_name', 'phone_number', 'district', 'role', 'is_active', 'date_joined']


class RegisterSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField()

    class Meta:
        model = PendingUser
        # faqat kerakli maydonlar
        fields = ['phone_number', 'first_name', 'last_name', 'district']

    def validate_phone_number(self, value):
        if not value.startswith("+998"):
            raise serializers.ValidationError("Telefon raqam +998 bilan boshlanishi kerak.")
        return value

    def create(self, validated_data):
        phone = validated_data['phone_number']

        # pending_user yaratish yoki yangilash
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

        # ⚡ OTP yaratish va jo'natish
        otp_code = OtpService.send_otp(phone, dev_mode=settings.DEBUG)

        # Cache ichida saqlash (ixtiyoriy)
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

        # OTP cache yoki service orqali tekshirish
        cached_code = cache.get(f"otp_{phone}")
        if cached_code != code:
            raise serializers.ValidationError("Noto‘g‘ri kod yoki telefon raqam.")

        # PendingUser mavjudligini tekshirish
        try:
            pending_user = PendingUser.objects.get(phone_number=phone)
        except PendingUser.DoesNotExist:
            raise serializers.ValidationError("Noto‘g‘ri kod yoki telefon raqam.")

        # OTP muvaffaqiyatli, expires_at tekshirish (ixtiyoriy)
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
    password = serializers.CharField(required=False, write_only=True)

    def validate_phone_number(self, value):
        if not value.startswith("+998"):
            raise serializers.ValidationError("Telefon raqam +998 bilan boshlanishi kerak.")
        return value

    def create(self, validated_data):
        phone = validated_data['phone_number']
        password = validated_data.get('password')

        # Foydalanuvchi mavjudligini tekshirish
        try:
            user = CustomUser.objects.get(phone_number=phone)
            # Dev modeda parol tekshiruvi
            if OtpService.DEV_MODE and password:
                if not user.check_password(password):
                    raise serializers.ValidationError("Parol noto‘g‘ri.")
        except CustomUser.DoesNotExist:
            # Foydalanuvchi mavjud emas → PendingUser yaratish
            user = PendingUser.objects.update_or_create(
                phone_number=phone,
                defaults={
                    'role': 'user',
                    'expires_at': timezone.now() + timedelta(minutes=5)
                }
            )[0]

        # OTP yuborish
        otp_code = OtpService.send_otp(phone, dev_mode=True)

        return {
            "user": {
                "id": getattr(user, 'id', None),
                "phone_number": phone
            },
            "otp": otp_code if OtpService.dev_mode else "****",
            "message": "OTP yuborildi"
        }

class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True)

class MedicalFileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = MedicalFile
        fields = ['id', 'user', 'file', 'uploaded_at']
