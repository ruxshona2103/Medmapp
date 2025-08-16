from rest_framework import serializers
from authentication.models import CustomUser
from .otp_service import OtpService
from rest_framework_simplejwt.tokens import RefreshToken


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'phone_number', 'full_name', 'role', 'is_active', 'date_joined']


class OtpRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField()

    def validate_phone_number(self, value):
        # Telefon formatini validatsiya qilsa ham bo‘ladi
        if not value.startswith("+998"):
            raise serializers.ValidationError("Telefon raqam +998 bilan boshlanishi kerak.")
        return value

    def create(self, validated_data):
        phone = validated_data['phone_number']

        # User yo‘q bo‘lsa yaratamiz
        user, created = CustomUser.objects.get_or_create(phone_number=phone)

        # OTP yuboramiz
        otp = OtpService.send_otp(phone, dev_mode=True)  # realda dev_mode=False qilasan

        # OTP ni vaqtinchalik saqlash (cache / db / redis ishlatish mumkin)
        from django.core.cache import cache
        cache.set(f"otp_{phone}", otp, timeout=300)  # 5 daqiqa amal qiladi

        return user


class OtpVerifySerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    code = serializers.CharField()

    def validate(self, data):
        phone = data['phone_number']
        code = data['code']

        from django.core.cache import cache
        cached_code = cache.get(f"otp_{phone}")

        if not cached_code:
            raise serializers.ValidationError("OTP muddati tugagan yoki yuborilmagan.")
        if cached_code != code:
            raise serializers.ValidationError("OTP noto‘g‘ri.")

        try:
            user = CustomUser.objects.get(phone_number=phone)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("Foydalanuvchi topilmadi.")

        data['user'] = user
        return data

    def create_token(self, user):
        refresh = RefreshToken.for_user(user)
        return {
            'user': UserSerializer(user).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }
