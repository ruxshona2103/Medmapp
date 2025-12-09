import asyncio
import json
import sys
import requests
from websockets import connect
from websockets.exceptions import WebSocketException


# ============================================================
# KONFIGURATSIYA (O'ZGARTIRING!)
# ============================================================

# Server URL lari
API_BASE_URL = "http://localhost:8000"  # Django HTTP server (JWT uchun)
WS_BASE_URL = "ws://localhost:8001"      # Daphne WebSocket server

# Test foydalanuvchi ma'lumotlari
TEST_USER = {
    "phone_number": "+998940984959",  # Real telefon raqam (SMS keladi)
    "first_name": "Test",              # Ism (register uchun)
    "last_name": "User"                # Familiya (register uchun)
}

# Avtomatik ro'yxatdan o'tkazish
AUTO_REGISTER = True  # True - kerak bo'lsa avtomatik register qiladi

# OTP kodni qo'lda kiritish yoki avtomatik
# INTERACTIVE MODE: Har safar SMS dan kelgan kodni kiritasiz
USE_MANUAL_OTP = False   # False - konsoldan so'raydi
MANUAL_OTP_CODE = ""     # Bo'sh - interactive mode ishlatiladi

# Test uchun conversation_id
# MUHIM: Bazada mavjud conversation_id ni kiriting!
# PostgreSQL orqali topish: SELECT id FROM consultations_conversation LIMIT 5;
TEST_CONVERSATION_ID = 1


# ============================================================
# YORDAMCHI FUNKSIYALAR
# ============================================================

def print_header(text):
    """Chiroyli sarlavha chiqarish"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_success(text):
    """Muvaffaqiyatli xabar (yashil)"""
    print(f"✅ {text}")


def print_error(text):
    """Xato xabari (qizil)"""
    print(f"❌ {text}")


def print_info(text):
    """Ma'lumot xabari"""
    print(f"ℹ️  {text}")


def register_user(phone_number, first_name="Test", last_name="User"):
    """
    0-QADAM: Foydalanuvchini ro'yxatdan o'tkazish

    Args:
        phone_number (str): Telefon raqam
        first_name (str): Ism
        last_name (str): Familiya

    Returns:
        bool: True (muvaffaqiyatli) yoki False (xato)
    """
    print_header("0. Foydalanuvchini Ro'yxatdan O'tkazish")

    try:
        url = f"{API_BASE_URL}/api/auth/register/"
        print_info(f"So'rov: POST {url}")
        print_info(f"Telefon: {phone_number}")
        print_info(f"Ism: {first_name} {last_name}")

        response = requests.post(
            url,
            json={
                "phone_number": phone_number,
                "first_name": first_name,
                "last_name": last_name
            },
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code == 201:
            data = response.json()
            print_success("Foydalanuvchi muvaffaqiyatli ro'yxatdan o'tdi!")
            print_info(f"Xabar: {data.get('message', '')}")
            return True
        elif response.status_code == 400:
            # User allaqachon ro'yxatdan o'tgan bo'lishi mumkin
            error_text = response.text
            if "ro'yxatdan o'tilgan" in error_text or "already exists" in error_text.lower():
                print_info("Foydalanuvchi allaqachon ro'yxatdan o'tgan.")
                return True
            else:
                print_error(f"Ro'yxatdan o'tishda xato! Status: {response.status_code}")
                print_error(f"Xato: {error_text}")
                return False
        else:
            print_error(f"Ro'yxatdan o'tishda xato! Status: {response.status_code}")
            print_error(f"Xato: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print_error(f"Serverga ulanib bo'lmadi: {API_BASE_URL}")
        print_error("Server ishga tushganini tekshiring!")
        return False
    except Exception as e:
        print_error(f"Kutilmagan xato: {str(e)}")
        return False


def request_otp(phone_number):
    """
    1-QADAM: OTP kodini so'rash

    Args:
        phone_number (str): Telefon raqam

    Returns:
        dict: API javobi yoki None (xato bo'lsa)
    """
    print_header("1. OTP Kodini So'rash")

    try:
        url = f"{API_BASE_URL}/api/auth/request-otp/"
        print_info(f"So'rov: POST {url}")
        print_info(f"Telefon: {phone_number}")

        response = requests.post(
            url,
            json={"phone_number": phone_number},
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            print_success("OTP muvaffaqiyatli so'ralindi!")
            print_info(f"Xabar: {data.get('message', '')}")

            # DEBUG rejimida OTP kod javobda bo'ladi
            if 'otp' in data and data['otp'] != "****":
                print_success(f"OTP Kod (DEBUG rejimi): {data['otp']}")
            else:
                print_info("OTP kod SMS orqali yuborildi (DEBUG=False)")
                print_info("SMS ga kuting yoki DEBUG=True qiling")

            return data
        else:
            print_error(f"OTP so'rashda xato! Status: {response.status_code}")
            print_error(f"Xato: {response.text}")
            return None

    except requests.exceptions.ConnectionError:
        print_error(f"Serverga ulanib bo'lmadi: {API_BASE_URL}")
        print_error("Server ishga tushganini tekshiring!")
        return None
    except Exception as e:
        print_error(f"Kutilmagan xato: {str(e)}")
        return None


def verify_otp(phone_number, otp_code):
    """
    2-QADAM: OTP kodni tasdiqlash va JWT token olish

    Args:
        phone_number (str): Telefon raqam
        otp_code (str): OTP kod

    Returns:
        str: Access token yoki None (xato bo'lsa)
    """
    print_header("2. OTP Tasdiqlash va JWT Token Olish")

    try:
        url = f"{API_BASE_URL}/api/auth/verify-otp/"
        print_info(f"So'rov: POST {url}")
        print_info(f"Telefon: {phone_number}")
        print_info(f"OTP Kod: {otp_code}")

        response = requests.post(
            url,
            json={
                "phone_number": phone_number,
                "code": otp_code
            },
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            access_token = data.get("access")

            if access_token:
                print_success("OTP tasdiqlandi! Token olindi!")
                print_info(f"Token: {access_token[:30]}...")
                print_info(f"User: {data.get('user', {}).get('phone_number', 'N/A')}")
                return access_token
            else:
                print_error("Javobda 'access' kaliti topilmadi")
                print_error(f"Javob: {data}")
                return None
        else:
            print_error(f"OTP tasdiqlashda xato! Status: {response.status_code}")
            print_error(f"Xato: {response.text}")
            return None

    except requests.exceptions.ConnectionError:
        print_error(f"Serverga ulanib bo'lmadi: {API_BASE_URL}")
        print_error("Server ishga tushganini tekshiring!")
        return None
    except Exception as e:
        print_error(f"Kutilmagan xato: {str(e)}")
        return None


async def test_websocket_connection(token):
    """
    3-QADAM: WebSocket ulanishini sinash

    Args:
        token (str): JWT access token
    """
    print_header("3. WebSocket Ulanishi")

    # WebSocket URL yaratish (token query parametr sifatida)
    # URL Pattern: ws://host/ws/chat/<conversation_id>/?token=<jwt_token>
    ws_url = f"{WS_BASE_URL}/ws/chat/{TEST_CONVERSATION_ID}/?token={token}"
    print_info(f"Ulanish: {WS_BASE_URL}/ws/chat/{TEST_CONVERSATION_ID}/?token=...")

    try:
        # WebSocket ga ulanish
        async with connect(ws_url) as websocket:
            print_success("WebSocket ulanishi muvaffaqiyatli!")

            # 4-QADAM: Test xabari yuborish
            print_header("4. Xabar Yuborish")
            test_message = {
                "message": "Salom! Bu test xabari WebSocket orqali.",
                "type": "text"
            }

            print_info(f"Yuborilmoqda: {json.dumps(test_message, ensure_ascii=False)}")
            await websocket.send(json.dumps(test_message))
            print_success("Xabar yuborildi!")

            # 5-QADAM: Broadcast javobini kutish
            print_header("5. Broadcast Javobini Kutish")
            print_info("Redis orqali broadcast qilingan xabarni kutmoqda (10 soniya)...")

            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                print_success("Broadcast javob olindi!")

                # JSON formatda chiqarish
                try:
                    response_data = json.loads(response)
                    print_info("Javob ma'lumotlari:")
                    print(json.dumps(response_data, indent=2, ensure_ascii=False))
                except json.JSONDecodeError:
                    print_info(f"Javob (matn): {response}")

            except asyncio.TimeoutError:
                print_error("Javob 10 soniya ichida kelmadi")
                print_info("Mumkin bo'lgan sabablar:")
                print_info("  - Redis ishlamayapti")
                print_info("  - Channel layer sozlanmagan")
                print_info("  - Consumer da xato bor")

            # 6-QADAM: Qo'shimcha test (emoji bilan)
            print_header("6. Qo'shimcha Test (Emoji)")
            test_message_2 = {
                "message": "Ikkinchi test xabari 🚀 Django Channels ishlayapti! ✅",
                "type": "text"
            }
            await websocket.send(json.dumps(test_message_2, ensure_ascii=False))
            print_success("Ikkinchi xabar yuborildi!")

            try:
                response_2 = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                response_data_2 = json.loads(response_2)
                print_success("Ikkinchi javob olindi!")
                print(json.dumps(response_data_2, indent=2, ensure_ascii=False))
            except asyncio.TimeoutError:
                print_info("Ikkinchi javob kelmadi (timeout)")

    except WebSocketException as e:
        print_error(f"WebSocket xatosi: {str(e)}")
        print_info("\n🔍 Mumkin bo'lgan sabablar:")
        print_info("  1. Daphne server ishlamayapti (port 8001)")
        print_info("     Yechim: daphne -b 0.0.0.0 -p 8001 config.asgi:application")
        print_info("  2. Token noto'g'ri yoki muddati tugagan")
        print_info("     Yechim: TEST_USER ma'lumotlarini tekshiring")
        print_info("  3. Conversation ID noto'g'ri yoki mavjud emas")
        print_info("     Yechim: PostgreSQL da conversation_id ni tekshiring")
        print_info("  4. Redis ishlamayapti")
        print_info("     Yechim: docker-compose up -d redis")

    except ConnectionRefusedError:
        print_error(f"WebSocket serverga ulanib bo'lmadi: {WS_BASE_URL}")
        print_info("\n🔧 Xatoni tuzatish:")
        print_info("  Terminal oynasida: daphne -b 0.0.0.0 -p 8001 config.asgi:application")

    except Exception as e:
        print_error(f"Kutilmagan xato: {str(e)}")
        import traceback
        traceback.print_exc()


# ============================================================
# ASOSIY DASTUR
# ============================================================

async def main():
    """Asosiy test funksiyasi"""
    print_header("WebSocket + OTP Authentication Test Boshlandi")
    print_info(f"API Server: {API_BASE_URL}")
    print_info(f"WebSocket Server: {WS_BASE_URL}")
    print_info(f"Conversation ID: {TEST_CONVERSATION_ID}")
    print_info(f"Test User: {TEST_USER['phone_number']}")
    print_info(f"Auto Register: {AUTO_REGISTER}")

    phone_number = TEST_USER['phone_number']
    first_name = TEST_USER.get('first_name', 'Test')
    last_name = TEST_USER.get('last_name', 'User')

    # 0. Register (agar kerak bo'lsa)
    if AUTO_REGISTER:
        registered = register_user(phone_number, first_name, last_name)
        if not registered:
            print_error("\nTest muvaffaqiyatsiz! Ro'yxatdan o'tish amalga oshmadi.")
            print_info("\n🔍 Xatoni tuzatish uchun:")
            print_info("  1. Django HTTP server ishga tushganini tekshiring")
            print_info("  2. Telefon raqam formatini tekshiring (+998...)")
            print_info("  3. AUTO_REGISTER=False qilib, qo'lda register qiling")
            sys.exit(1)

    # 1. OTP so'rash
    otp_response = request_otp(phone_number)
    if not otp_response:
        print_error("\nTest muvaffaqiyatsiz! OTP so'rash amalga oshmadi.")
        print_info("\n🔍 Xatoni tuzatish uchun:")
        print_info("  1. Django HTTP server ishga tushganini tekshiring:")
        print_info("     python manage.py runserver 0.0.0.0:8000")
        print_info("  2. Telefon raqam bazada ro'yxatdan o'tganmi?")
        print_info("     Agar yo'q bo'lsa: POST /api/auth/register/")
        print_info("  3. SMS servis ishlab turibdimi? (Eskiz.uz)")
        sys.exit(1)

    # 2. OTP kodni olish (DEBUG yoki manual)
    otp_code = None

    # DEBUG rejimda OTP javobda bo'ladi
    if 'otp' in otp_response and otp_response['otp'] != "****":
        otp_code = otp_response['otp']
        print_info(f"\n🔐 DEBUG rejimidan OTP ishlatiladi: {otp_code}")

    # Manual OTP
    elif USE_MANUAL_OTP:
        if MANUAL_OTP_CODE:
            otp_code = MANUAL_OTP_CODE
            print_info(f"\n🔐 Qo'lda kiritilgan OTP ishlatiladi: {otp_code}")
        else:
            print_info("\n📱 Iltimos, SMS dagi OTP kodni kiriting:")
            otp_code = input("OTP kod: ").strip()

    # Input so'rash (faqat interactive mode da)
    else:
        try:
            print_info("\n📱 SMS dagi OTP kodni kiriting (yoki Enter bosing, Django loglardan olish uchun):")
            user_input = input("OTP kod: ").strip()
            if user_input:
                otp_code = user_input
            else:
                # Django logs dan olishni taklif qiling
                print_error("OTP kod kiritilmadi!")
                print_info("DEBUG=True bo'lsa, Django server loglarida OTP kod ko'rinadi.")
                print_info("Yoki MANUAL_OTP_CODE ni to'g'ridan-to'g'ri skriptda yozing.")
                sys.exit(1)
        except (EOFError, KeyboardInterrupt):
            # Non-interactive mode (pipe, automation, etc.)
            print_error("\nNon-interactive mode aniqlandi!")
            print_info("OTP kodni avtomatik olish uchun quyidagilardan birini qiling:")
            print_info("  1. DEBUG=True qiling (tavsiya etiladi)")
            print_info("  2. USE_MANUAL_OTP=True va MANUAL_OTP_CODE yozing")
            print_info("  3. Django server loglaridan OTP kodini topib, skriptni qayta ishga tushiring")
            sys.exit(1)

    if not otp_code or len(otp_code) != 6:
        print_error("OTP kod 6 ta raqam bo'lishi kerak!")
        sys.exit(1)

    # 3. OTP tasdiqlash va token olish
    token = verify_otp(phone_number, otp_code)
    if not token:
        print_error("\nTest muvaffaqiyatsiz! OTP tasdiqlanmadi yoki token olinmadi.")
        print_info("\n🔍 Xatoni tuzatish uchun:")
        print_info("  1. OTP kod to'g'rimi?")
        print_info("  2. OTP muddati tugaganmi? (5 daqiqa)")
        print_info("  3. 3 marta xato kiritdingizmi?")
        sys.exit(1)

    # 4. WebSocket test
    await test_websocket_connection(token)

    # Yakuniy xabar
    print_header("Test Tugadi")
    print_success("Barcha testlar bajarildi!")
    print_info("\n📋 Keyingi qadamlar:")
    print_info("  1. Agar xato bo'lsa, yuqoridagi xato xabarlarini o'qing")
    print_info("  2. Docker containerlarni tekshiring: docker-compose ps")
    print_info("  3. Redis loglarini ko'ring: docker-compose logs redis")
    print_info("  4. Daphne loglarini ko'ring (agar Docker da ishlatgan bo'lsangiz)")
    print_info("  5. Django HTTP loglarini terminal oynasida kuzating")
    print_info("\n✨ Agar hamma narsa ishlasa, frontend ga o'tishingiz mumkin!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test foydalanuvchi tomonidan to'xtatildi (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        print_error(f"\nUmumiy xato: {str(e)}")
        sys.exit(1)
