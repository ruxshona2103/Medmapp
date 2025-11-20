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
import requests  # SMS yuborish uchun
import random  # OTP generatsiya uchun

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

        # Agar oxirgi 60 soniyada OTP yuborilgan bo'lsa, qayta yubormaslik (spam oldini olish)
        last_sent = cache.get(f"otp_last_sent_{phone}")
        if last_sent:
            time_passed = (timezone.now() - last_sent).total_seconds()
            if time_passed < 60:
                wait_time = int(60 - time_passed)
                raise serializers.ValidationError(
                    f"OTP allaqachon yuborilgan. {wait_time} soniyadan keyin qayta so'rang."
                )

        # 1. OTP generatsiya qilish
        otp_code = str(random.randint(100000, 999999))

        print(f"🔑 Generated OTP: {otp_code} for phone: {phone}")

        # 2. AVVAL cache'ga saqlash va VERIFY qilish
        cache.set(f"otp_{phone}", otp_code, timeout=300)  # 5 daqiqa
        cache.set(f"otp_attempts_{phone}", 0, timeout=300)  # Urinishlarni reset
        cache.set(f"otp_last_sent_{phone}", timezone.now(), timeout=300)  # Oxirgi yuborish vaqti

        # MUHIM: Cache'ga yozilganini verify qilish
        import time
        time.sleep(0.1)  # 100ms kutish - database cache commit uchun

        # Verify cache
        cached_check = cache.get(f"otp_{phone}")
        if cached_check != otp_code:
            print(f"⚠️ CACHE XATOLIK! Saqlanmadi. Saved: {otp_code}, Retrieved: {cached_check}")
            raise serializers.ValidationError("Server xatolik: Cache ishlamayapti. Administrator bilan bog'laning.")

        print(f"✅ Cache verified: {cached_check}")

        # 3. SMS yuborish
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
            print(f"✅ SMS yuborildi: {phone}")
        except Exception as e:
            print(f"⚠️ SMS yuborishda xatolik: {e}")

            # Production'da xatolik bo'lsa cache'ni tozalash
            if not settings.DEBUG:
                cache.delete(f"otp_{phone}")
                cache.delete(f"otp_attempts_{phone}")
                cache.delete(f"otp_last_sent_{phone}")
                raise serializers.ValidationError("SMS yuborishda xatolik yuz berdi. Qayta urinib ko'ring.")

        return {
            "message": "OTP muvaffaqiyatli yuborildi!",
            "phone_number": phone,
            "otp": otp_code if settings.DEBUG else "****",
            "cache_ready": True,
            "sms_sent": sms_sent,
            "estimated_delivery": "5-30 soniya",
        }


class OtpVerifySerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    code = serializers.CharField()

    def validate(self, attrs):
        phone = attrs.get("phone_number")
        code = attrs.get("code", "").strip()  # Bo'sh joylarni olib tashlash

        print(f"🔍 Verify OTP: phone={phone}, code={code}")

        # Cache'dan OTP olish
        cached_code = cache.get(f"otp_{phone}")

        print(f"🔍 Cached code: {cached_code}")

        if not cached_code:
            print(f"❌ Cache bo'sh! Phone: {phone}")
            raise serializers.ValidationError(
                "OTP topilmadi yoki muddati tugagan. Iltimos, yangi OTP so'rang."
            )

        # Urinishlarni tekshirish (max 3 urinish)
        attempts = cache.get(f"otp_attempts_{phone}", 0)
        print(f"🔍 Attempts: {attempts}")

        if attempts >= 3:
            # OTP ni o'chirish
            cache.delete(f"otp_{phone}")
            cache.delete(f"otp_attempts_{phone}")
            cache.delete(f"otp_last_sent_{phone}")
            print(f"❌ Maksimal urinishlar tugadi: {phone}")
            raise serializers.ValidationError("Maksimal urinishlar soni tugadi. Iltimos, yangi OTP so'rang.")

        # Kodni solishtirish - ANIQ solishtirish
        cached_code_clean = str(cached_code).strip()
        input_code_clean = str(code).strip()

        print(f"🔍 Comparing: cached='{cached_code_clean}' vs input='{input_code_clean}'")

        if cached_code_clean != input_code_clean:
            # Urinishlarni oshirish
            new_attempts = attempts + 1
            cache.set(f"otp_attempts_{phone}", new_attempts, timeout=300)
            print(f"❌ Kod noto'g'ri! Attempts: {new_attempts}")
            raise serializers.ValidationError(f"Noto'g'ri kod. Qolgan urinishlar: {3 - new_attempts}")

        print(f"✅ Kod to'g'ri!")

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
        cache.delete(f"otp_last_sent_{phone}")
        cache.delete(f"otp_ready_{phone}")  # Cache tayyor signalini ham o'chirish

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
        cache.delete(f"otp_ready_{phone}")  # Cache tayyor signalini ham o'chirish

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























