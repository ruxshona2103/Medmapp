import os
from pathlib import Path
from datetime import timedelta
import dj_database_url
from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv

# ===============================================================
# 1. LOAD ENVIRONMENT VARIABLES
# ===============================================================
# .env faylni yuklaymiz. Serverda bu fayl bo'lmasa, Environment Variablelardan oladi.
load_dotenv()

# ===============================================================
# 2. BASE CONFIGURATION
# ===============================================================
BASE_DIR = Path(__file__).resolve().parent.parent

# Maxfiy kalit .env dan olinadi, topilmasa default (faqat dev uchun) qo'yiladi
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-dev-key-change-in-prod")

# Environmentni aniqlash
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT == "production"

# Debug rejimi (Stringni Booleanga o'girish)
DEBUG = os.environ.get("DEBUG", "False").lower() == "true"


# ===============================================================
# 3. HOSTS & SECURITY
# ===============================================================
# Vergul bilan ajratilgan stringni listga aylantiramiz
def get_list(text):
    if not text:
        return []
    return [item.strip() for item in text.split(",")]


ALLOWED_HOSTS = get_list(os.environ.get("ALLOWED_HOSTS", "127.0.0.1,localhost"))

# ===============================================================
# 4. INSTALLED APPS
# ===============================================================
INSTALLED_APPS = [
    "daphne",  # WebSocket server - BIRINCHI bo'lishi kerak!
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third party apps
    "channels",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_yasg",

    # Local apps
    "authentication",
    "patients.apps.PatientsConfig",
    "partners.apps.PartnersConfig",
    "applications",
    "services",
    "consultations",
    "clinics",
    "core",
    "review",
]

# ===============================================================
# 5. MIDDLEWARE
# ===============================================================
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # Eng tepada
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Static files uchun
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

# ===============================================================
# 6. TEMPLATES
# ===============================================================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ===============================================================
# 7. AUTH USER MODEL
# ===============================================================
AUTH_USER_MODEL = "authentication.CustomUser"

# ===============================================================
# 8. DATABASE (SMART SWITCHING)
# ===============================================================
# Mantiq:
# 1. Serverda (IS_PRODUCTION=True) -> PostgreSQL talab qilinadi.
# 2. Lokalda (IS_PRODUCTION=False) -> Agar DATABASE_URL berilmagan bo'lsa, SQLite ishlatadi.

if IS_PRODUCTION:
    # 🌍 PRODUCTION (PostgreSQL)
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("CRITICAL: Production muhitida DATABASE_URL topilmadi!")

    DATABASES = {
        "default": dj_database_url.config(
            default=database_url,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=True,  # Render/Cloud uchun xavfsizlik
        )
    }
else:
    # 💻 DEVELOPMENT (SQLite default)
    # Agar .env da DATABASE_URL bo'lsa, o'shani ishlatadi, bo'lmasa SQLite.
    DATABASES = {
        "default": dj_database_url.config(
            default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
            conn_max_age=600,
        )
    }

# ===============================================================
# 9. PASSWORD VALIDATION
# ===============================================================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ===============================================================
# 10. INTERNATIONALIZATION
# ===============================================================
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Tashkent"  # O'zbekiston vaqti
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ("uz", _("Uzbek")),
    ("ru", _("Russian")),
    ("en", _("English")),
]
LOCALE_PATHS = [BASE_DIR / "locale"]

# ===============================================================
# 11. STATIC & MEDIA FILES
# ===============================================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# WhiteNoise settings
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ===============================================================
# 12. CORS & CSRF
# ===============================================================
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = get_list(os.environ.get("CORS_ALLOWED_ORIGINS"))
CSRF_TRUSTED_ORIGINS = get_list(os.environ.get("CSRF_TRUSTED_ORIGINS"))

CORS_ALLOW_HEADERS = ["*"]
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

# ===============================================================
# 13. REST FRAMEWORK (JWT)
# ===============================================================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication"
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly"
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

if DEBUG:
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"].append(
        "rest_framework.renderers.BrowsableAPIRenderer"
    )

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ===============================================================
# 14. SWAGGER
# ===============================================================
SWAGGER_SETTINGS = {
    "USE_SESSION_AUTH": False,
    "SECURITY_DEFINITIONS": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
        }
    },
}

# ===============================================================
# 15. REDIS & CHANNELS
# ===============================================================
REDIS_URL = os.environ.get("REDIS_URL")

if IS_PRODUCTION and REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_URL],
            },
        },
    }
else:
    # Lokalda Redis shart emas, xotirada ishlaydi
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }

# ===============================================================
# 16. SECURITY (HTTPS)
# ===============================================================
if IS_PRODUCTION:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True