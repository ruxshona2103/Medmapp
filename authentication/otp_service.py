import requests
import random


class OtpService:
    LOGIN_EMAIL = "yuldoshovich@mail.ru"
    LOGIN_PASSWORD = "LybZx7ZSH6Uavso90lwRKZagdc5DDvBVKlfFNmi4"
    LOGIN_URL = "https://notify.eskiz.uz/api/auth/login"
    SMS_URL = "https://notify.eskiz.uz/api/message/sms/send"
    FROM = "4546"

    @staticmethod
    def _generate_otp():
        return str(random.randint(100000, 999999))

    @classmethod
    def send_otp(cls, phone: str, dev_mode=False) -> str:
        otp = cls._generate_otp()
        if dev_mode:
            print(f"[DEV] OTP: {otp} -> {phone}")
            return otp

        # Token olish
        login_response = requests.post(
            cls.LOGIN_URL,
            data={"email": cls.LOGIN_EMAIL, "password": cls.LOGIN_PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        login_response.raise_for_status()
        token = login_response.json().get("data", {}).get("token")
        if not token:
            raise Exception("Eskiz tokenini olishda xatolik yuz berdi.")

        # SMS yuborish
        payload = {
            "mobile_phone": phone,
            "message": f"Kelishamiz.uz saytiga ro‘yxatdan o‘tish uchun tasdiqlash kodi: {otp}",
            "from": cls.FROM
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        response = requests.post(cls.SMS_URL, json=payload, headers=headers)
        response.raise_for_status()
        print(f"✅ OTP {otp} yuborildi -> {phone}")
        return otp
