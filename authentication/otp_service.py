import requests
import random
import time

class OtpService:
    _token_data = None

    ESKIZ_EMAIL = "yuldoshovich@mail.ru"
    ESKIZ_PASSWORD = "0GzjPHd6pBn1jH83"
    LOGIN_URL = "https://notify.eskiz.uz/api/auth/login"
    SMS_URL = "https://notify.eskiz.uz/api/message/sms/send"

    @classmethod
    def _fetch_token(cls):
        data = {
            "email": cls.ESKIZ_EMAIL,
            "password": cls.ESKIZ_PASSWORD,
        }
        response = requests.post(cls.LOGIN_URL, data=data)
        response.raise_for_status()

        token = response.json().get("data", {}).get("token")
        if not token:
            raise Exception("Eskiz.uz API tokenini olishda xatolik yuz berdi.")

        expires_in = 24 * 60 * 60  # 24 soat
        expires_at = int(time.time()) + expires_in - 60  # 1 daqiqa zaxira

        cls._token_data = {"token": token, "expires_at": expires_at}
        return token

    @classmethod
    def _get_token(cls):
        if not cls._token_data or int(time.time()) >= cls._token_data["expires_at"]:
            return cls._fetch_token()
        return cls._token_data["token"]

    @staticmethod
    def _generate_otp():
        """6 xonali OTP"""
        return str(random.randint(100000, 999999))


    @classmethod
    def send_otp(cls, phone: str, dev_mode=True) -> str:
        """
        dev_mode=True -> Swagger yoki testda ishlatish uchun
        har doim '123456' OTP qaytadi
        dev_mode=False -> real SMS yuboradi
        """
        if dev_mode:
            otp = "123456"
            print(f"[DEV] OTP: {otp} -> {phone}")
            return otp

        # production rejimida real OTP yuboramiz
        otp = str(time.time())[-6:]  # vaqt asosida random-like 6 xonali kod
        token = cls._get_token()
        payload = {
            "mobile_phone": phone,
            "message": f"MedMap tizimiga kirish uchun kod: {otp}",
            "from": "4546"
        }

        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(cls.SMS_URL, json=payload, headers=headers)
        response.raise_for_status()

        print(f"[PROD] OTP {otp} yuborildi -> {phone}")
        return otp