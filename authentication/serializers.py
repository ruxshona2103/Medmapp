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
            raise serializers.ValidationError("Avval ro'yxatdan o'ting.")
        return value

    def create(self, validated_data):
        phone = validated_data["phone_number"]

        # Cache'ga AVVAL saqlash (race condition oldini olish)
        otp_code = OtpService.send_otp(phone)
        cache.set(f"otp_{phone}", otp_code, timeout=300)  # 5 daqiqa
        cache.set(f"otp_attempts_{phone}", 0, timeout=300)  # Urinishlarni reset

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
        code = attrs.get("code", "").strip()  # Bo'sh joylarni olib tashlash

        # Cache'dan OTP olish
        cached_code = cache.get(f"otp_{phone}")

        if not cached_code:
            raise serializers.ValidationError("OTP yuborilmagan yoki muddati tugagan.")

        # Urinishlarni tekshirish (max 3 urinish)
        attempts = cache.get(f"otp_attempts_{phone}", 0)
        if attempts >= 3:
            # OTP ni o'chirish
            cache.delete(f"otp_{phone}")
            cache.delete(f"otp_attempts_{phone}")
            raise serializers.ValidationError("Maksimal urinishlar soni tugadi. Iltimos, yangi OTP so'rang.")

        # Kodni solishtirish (strip qilingan)
        if str(cached_code).strip() != str(code).strip():
            # Urinishlarni oshirish
            cache.set(f"otp_attempts_{phone}", attempts + 1, timeout=300)
            raise serializers.ValidationError(f"Noto'g'ri kod. Qolgan urinishlar: {2 - attempts}")

        try:
            pending = PendingUser.objects.get(phone_number=phone)
        except PendingUser.DoesNotExist:
            if not CustomUser.objects.filter(phone_number=phone).exists():
                raise serializers.ValidationError("Bunday raqam uchun ro'yxatdan o'tish topilmadi.")

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

        # MUHIM: OTP ishlatilgandan keyin cache'dan o'chirish
        cache.delete(f"otp_{phone}")
        cache.delete(f"otp_attempts_{phone}")

        return user


class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    code = serializers.CharField()

    def validate(self, attrs):
        phone = attrs.get("phone_number")
        code = attrs.get("code", "").strip()  # Bo'sh joylarni olib tashlash

        cached_otp = cache.get(f"otp_{phone}")
        if not cached_otp:
            raise serializers.ValidationError({"detail": "OTP muddati tugagan yoki yuborilmagan."})

        # Urinishlarni tekshirish (max 3 urinish)
        attempts = cache.get(f"otp_attempts_{phone}", 0)
        if attempts >= 3:
            cache.delete(f"otp_{phone}")
            cache.delete(f"otp_attempts_{phone}")
            raise serializers.ValidationError({"detail": "Maksimal urinishlar soni tugadi. Iltimos, yangi OTP so'rang."})

        # Kodni solishtirish (strip qilingan)
        if str(code).strip() != str(cached_otp).strip():
            cache.set(f"otp_attempts_{phone}", attempts + 1, timeout=300)
            raise serializers.ValidationError({"detail": f"Noto'g'ri kod. Qolgan urinishlar: {2 - attempts}"})

        try:
            user = User.objects.get(phone_number=phone)
        except User.DoesNotExist:
            raise serializers.ValidationError({"detail": "Bunday foydalanuvchi topilmadi, oldin ro'yxatdan o'ting."})

        # OTP ishlatilgandan keyin o'chirish
        cache.delete(f"otp_{phone}")
        cache.delete(f"otp_attempts_{phone}")

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


# --------------------------------------------PARTNET PANEL-------------------------------------------------------------


class PartnerLoginSerializer(TokenObtainPairSerializer):
    """
    Partner login - oddiy versiya

    1. Bazadan user topish (phone_number)
    2. Parolni tekshirish
    3. Role='partner' tekshirish
    4. Token berish
    """

    @classmethod
    def get_token(cls, user):
        """JWT token yaratish"""
        token = super().get_token(user)

        # Custom claims
        token['role'] = user.role
        token['phone_number'] = user.phone_number

        # Partner profile (agar bo'lsa)
        if hasattr(user, 'partner_profile'):
            token['partner_id'] = user.partner_profile.id
            token['partner_name'] = user.partner_profile.name

        return token

    def validate(self, attrs):
        """
        Validation:
        1. Parent class parol tekshiradi
        2. Biz faqat role tekshiramiz
        """
        # Parent class authenticate qiladi (phone_number + password)
        data = super().validate(attrs)

        # Role tekshirish
        if self.user.role != 'partner':
            raise AuthenticationFailed(
                "Faqat hamkorlar login qila oladi. Sizning role: {}".format(self.user.role)
            )

        # User ma'lumotlarini qaytarish
        data['user'] = {
            'id': self.user.id,
            'phone_number': self.user.phone_number,
            'role': self.user.role,
            'first_name': self.user.first_name or '',
            'last_name': self.user.last_name or '',
        }

        # Partner profile (agar bo'lsa)
        if hasattr(self.user, 'partner_profile'):
            data['user']['partner_id'] = self.user.partner_profile.id
            data['user']['partner_name'] = self.user.partner_profile.name
            data['user']['partner_code'] = self.user.partner_profile.code

        return data























