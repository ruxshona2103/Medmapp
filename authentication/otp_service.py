# import requests
# import random
# import os
#
#
# class OtpService:
#     LOGIN_EMAIL = os.environ.get("ESKIZ_EMAIL", "mirakovshohjahon@gmail.com")
#     LOGIN_PASSWORD = os.environ.get("ESKIZ_PASSWORD", "83VFXt3C1R5Pdgeti2ZrTlEBxB6SYNREz9bV3nrr")
#     LOGIN_URL = "https://notify.eskiz.uz/api/auth/login"
#     SMS_URL = "https://notify.eskiz.uz/api/message/sms/send"
#     FROM = "4546"
#
#     _token = None
#     _token_expires_at = 0
#
#     @staticmethod
#     def _generate_otp():
#         return str(random.randint(100000, 999999))
#
#     @classmethod
#     def _get_token(cls):
#         """Tokenni olish yoki yangilash uchun ichki metod."""
#         if not cls._token or cls._token_expires_at <= requests.models.datetime.datetime.now().timestamp():
#             try:
#                 login_response = requests.post(
#                     cls.LOGIN_URL,
#                     data={"email": cls.LOGIN_EMAIL, "password": cls.LOGIN_PASSWORD},
#                     headers={"Content-Type": "application/x-www-form-urlencoded"},
#                     timeout=10
#                 )
#                 login_response.raise_for_status()
#                 response_data = login_response.json()
#                 cls._token = response_data.get("data", {}).get("token")
#
#                 cls._token_expires_at = requests.models.datetime.datetime.now().timestamp() + 23 * 60 * 60
#
#                 if not cls._token:
#                     raise Exception("Eskiz tokenini olishda xatolik yuz berdi: 'token' kaliti topilmadi.")
#
#                 print("✅ Eskiz.uz tokeni muvaffaqiyatli yangilandi.")
#
#             except requests.exceptions.RequestException as e:
#                 raise Exception(f"Eskiz.uz API ga ulanishda xatolik yuz berdi: {e}")
#             except Exception as e:
#                 raise e
#
#         return cls._token
#
#     @classmethod
#     def send_otp(cls, phone: str) -> str:
#         """Berilgan raqamga OTP yuborish. Faqat haqiqiy SMS yuboriladi."""
#         otp = cls._generate_otp()
#
#         token = cls._get_token()
#
#         payload = {
#             "mobile_phone": phone,
#             "message": f"medmapp.uz platformasiga kirish uchun tasdiqlash kodi: {otp}",
#             "from": cls.FROM
#         }
#         headers = {
#             "Authorization": f"Bearer {token}",
#             "Content-Type": "application/json"
#         }
#
#         try:
#             response = requests.post(cls.SMS_URL, json=payload, headers=headers, timeout=10)
#             response.raise_for_status()
#             print(f"✅ OTP {otp} raqamiga yuborildi: {phone}")
#             return otp
#         except requests.exceptions.RequestException as e:
#             raise Exception(f"SMS yuborishda xatolik yuz berdi: {e}")

import random
import os


class OtpService:
    @staticmethod
    def _generate_otp():
        """6 xonali tasodifiy OTP generatsiya qiladi."""
        return str(random.randint(100000, 999999))

    @classmethod
    def send_otp(cls, phone: str) -> str:
        """Berilgan raqamga fake OTP qaytaradi (haqiqiy SMS yuborilmaydi)."""
        otp = cls._generate_otp()
        return otp