from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import serializers
from authentication.models import CustomUser, MedicalFile, PendingUser
from config import settings
from django.utils import timezone
from datetime import timedelta
from .otp_service import OtpService
from .otp_manager import OTPManager
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed
import requests
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'first_name', 'last_name', 'phone_number', 'district', 'role', 'is_active', 'date_joined']
        ref_name = "AuthUserSerializer"


class RegisterSerializer(serializers.ModelSerializer):
    """
    FIXED: Phone normalization added for consistency
    """
    phone_number = serializers.CharField()

    class Meta:
        model = PendingUser
        fields = ['phone_number', 'first_name', 'last_name', 'district']

    def validate_phone_number(self, value):
        # ✅ NORMALIZE phone number (CRITICAL FIX!)
        value = OTPManager.normalize_phone(value)
        logger.info(f"📝 Register: normalized phone = {value}")

        if not value.startswith("+998"):
            raise serializers.ValidationError("Telefon raqam +998 bilan boshlanishi kerak")

        # Check against normalized phone
        if CustomUser.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("Bu raqam bilan ro'yxatdan o'tilgan")

        # Also check PendingUser (allow update)
        if PendingUser.objects.filter(phone_number=value).exists():
            logger.info(f"ℹ️ PendingUser already exists for {value}, will update")

        return value

    def create(self, validated_data):
        phone = validated_data['phone_number']
        logger.info(f"📝 Creating PendingUser for {phone}")

        pending_user, created = PendingUser.objects.update_or_create(
            phone_number=phone,
            defaults={
                "first_name": validated_data.get("first_name", ""),
                "last_name": validated_data.get("last_name", ""),
                "district": validated_data.get("district", ""),
                "role": "user",
                "expires_at": timezone.now() + timedelta(minutes=5),
            }
        )

        if created:
            logger.info(f"✅ New PendingUser created: {phone}")
        else:
            logger.info(f"♻️ PendingUser updated: {phone}")

        return pending_user


class OtpRequestSerializer(serializers.Serializer):
    """
    BULLETPROOF OTP Request Serializer
    - Dual storage (Cache + DB)
    - Thread-safe
    - Proper error handling
    """
    phone_number = serializers.CharField()

    def validate_phone_number(self, value):
        # Normalize phone number
        original_value = value
        value = OTPManager.normalize_phone(value)
        logger.info(f"📞 OTP Request: original={original_value}, normalized={value}")

        if not value.startswith("+998"):
            raise serializers.ValidationError("Telefon raqam +998 bilan boshlanishi kerak.")

        # Check if user exists with detailed logging
        pending_exists = PendingUser.objects.filter(phone_number=value).exists()
        custom_exists = CustomUser.objects.filter(phone_number=value).exists()

        logger.info(f"🔍 User check for {value}: PendingUser={pending_exists}, CustomUser={custom_exists}")

        if not (pending_exists or custom_exists):
            # Additional debug: check what's actually in the database
            pending_count = PendingUser.objects.count()
            custom_count = CustomUser.objects.count()
            logger.error(f"❌ User not found for {value}! (PendingUsers: {pending_count}, CustomUsers: {custom_count})")

            # Try to find similar phones (debug)
            similar = PendingUser.objects.filter(phone_number__contains="998").values_list('phone_number', flat=True)[:5]
            logger.error(f"📋 Similar phones in DB: {list(similar)}")

            raise serializers.ValidationError("Avval ro'yxatdan o'ting.")

        logger.info(f"✅ User found for {value}")
        return value

    def create(self, validated_data):
        phone = validated_data["phone_number"]
        logger.info(f"📞 OTP request for {phone}")

        try:
            # Create OTP using bulletproof manager (dual storage)
            otp_code, success = OTPManager.create_otp(phone)

            if not success:
                raise serializers.ValidationError("OTP yaratishda xatolik yuz berdi.")

            logger.info(f"🔐 OTP created for {phone}: {otp_code if settings.DEBUG else '****'}")

        except ValueError as e:
            # Cooldown or other validation error
            logger.warning(f"⏳ OTP creation blocked for {phone}: {str(e)}")
            raise serializers.ValidationError(str(e))
        except Exception as e:
            logger.error(f"❌ OTP creation error for {phone}: {e}")
            raise serializers.ValidationError("Server xatolik. Iltimos, qayta urinib ko'ring.")

        # Send SMS
        sms_sent = False
        try:
            token = OtpService._get_token()

            payload = {
                "mobile_phone": phone,
                "message": f"medmapp.uz platformasiga kirish uchun tasdiqlash kodi: {otp_code}",
                "from": "4546"
            }
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            response = requests.post(
                "https://notify.eskiz.uz/api/message/sms/send",
                json=payload,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            sms_sent = True
            logger.info(f"✉️ SMS sent successfully to {phone}")

        except Exception as e:
            logger.error(f"❌ SMS sending error for {phone}: {e}")

            # SMS failed - cleanup OTP using CORRECT method name
            OTPManager._cleanup_specific_otp(phone)  # ✅ FIXED: was _cleanup_otp

            # Always raise error if SMS fails (even in DEBUG)
            raise serializers.ValidationError(
                "SMS yuborishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring."
            )

        return {
            "message": "OTP muvaffaqiyatli yuborildi!",
            "phone_number": phone,
            "otp": otp_code if settings.DEBUG else "****",
            "sms_sent": sms_sent,
            "estimated_delivery": "5-30 soniya",
        }


class OtpVerifySerializer(serializers.Serializer):
    """
    BULLETPROOF OTP Verify Serializer
    - Dual storage fallback (Cache -> DB)
    - Timing-safe comparison
    - Thread-safe
    - Comprehensive logging
    """
    phone_number = serializers.CharField()
    code = serializers.CharField()

    def validate(self, attrs):
        phone = attrs.get("phone_number")
        code = attrs.get("code", "").strip()

        # Normalize phone
        phone = OTPManager.normalize_phone(phone)
        attrs["phone_number"] = phone

        logger.info(f"🔍 Verifying OTP for {phone}, code length: {len(code)}")

        # ✅ Validate code format
        if not code or not code.isdigit() or len(code) != 6:
            logger.warning(f"❌ Invalid OTP format for {phone}: length={len(code)}, isdigit={code.isdigit()}")
            raise serializers.ValidationError("OTP 6 ta raqamdan iborat bo'lishi kerak")

        # Verify using bulletproof manager
        success, message = OTPManager.verify_otp(phone, code)

        if not success:
            logger.warning(f"❌ OTP verification failed for {phone}: {message}")
            raise serializers.ValidationError(message)

        logger.info(f"✅ OTP verified successfully for {phone}")

        # Get or check pending user
        try:
            pending = PendingUser.objects.get(phone_number=phone)
            attrs["pending_user"] = pending
            logger.info(f"📋 PendingUser found for {phone}")
        except PendingUser.DoesNotExist:
            # Check if user already exists
            if not CustomUser.objects.filter(phone_number=phone).exists():
                logger.error(f"❌ No PendingUser or CustomUser for {phone}")
                raise serializers.ValidationError("Bunday raqam uchun ro'yxatdan o'tish topilmadi.")
            attrs["pending_user"] = None
            logger.info(f"ℹ️ Existing CustomUser login for {phone}")

        return attrs

    def create(self, validated_data):
        pending = validated_data.get("pending_user")
        phone = validated_data.get("phone_number")

        logger.info(f"👤 Creating/updating user for {phone}")

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

        if created:
            logger.info(f"✅ New user created: {phone}")
        else:
            logger.info(f"🔓 Existing user logged in: {phone}")

        # OTP already cleaned up by OTPManager.verify_otp()
        return user


class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    code = serializers.CharField()

    def validate(self, attrs):
        phone = attrs.get("phone_number")
        code = attrs.get("code", "").strip()

        cached_otp = cache.get(f"otp_{phone}")
        if not cached_otp:
            raise serializers.ValidationError({"detail": "OTP muddati tugagan yoki yuborilmagan."})

        # Urinishlarni tekshirish (max 3 urinish)
        attempts = cache.get(f"otp_attempts_{phone}", 0)
        if attempts >= 3:
            cache.delete(f"otp_{phone}")
            cache.delete(f"otp_attempts_{phone}")
            cache.delete(f"otp_ready_{phone}")
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
        cache.delete(f"otp_last_sent_{phone}")
        cache.delete(f"otp_ready_{phone}")

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
    Token ichiga role, phone_number va full_name qo'shamiz.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Qo'shimcha claimlar
        token['role'] = user.role
        token['phone_number'] = user.phone_number
        token['full_name'] = user.get_full_name()
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        # User haqida qo'shimcha info response'da qaytsin
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


# --------------------------------------------PARTNER PANEL-------------------------------------------------------------


class OperatorProfileSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    role = serializers.CharField(source='user.role', read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        from authentication.models import OperatorProfile
        model = OperatorProfile
        fields = [
            'id',
            'phone_number',
            'role',
            'full_name',
            'avatar',
            'avatar_url',
            'employee_id',
            'department',
            'phone',
            'email',
            'is_active',
            'total_patients_processed',
            'total_applications_processed',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'employee_id',
            'total_patients_processed',
            'total_applications_processed',
            'created_at',
            'updated_at',
            'avatar_url',
        ]
        extra_kwargs = {
            'avatar': {'write_only': True},
        }

    def get_avatar_url(self, obj):
        """Avatar URL qaytarish"""
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None


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