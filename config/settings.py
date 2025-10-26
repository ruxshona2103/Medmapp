# ===============================================================
# SETTINGS.PY - LOCAL VA PRODUCTION UCHUN
# ===============================================================

import os
from datetime import timedelta
from pathlib import Path
import dj_database_url
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent

# ==========================
# 🔐 SECURITY SETTINGS
# ==========================
SECRET_KEY = "django-insecure-2_yzlz!b-z%j+p4e^^^!ewhmg%5r==5u)24t*s+j^xun80s14_"

# Environment detection
IS_PRODUCTION = os.environ.get('ENVIRONMENT') == 'production'
DEBUG = not IS_PRODUCTION  # Production'da False, local'da True

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "medmapp-1pjj.onrender.com",
]

# ==========================
# 🌍 INTERNATIONALIZATION
# ==========================
LANGUAGES = [
    ("uz", _("Uzbek")),
    ("ru", _("Russian")),
    ("en", _("English")),
]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ==========================
# 📦 INSTALLED APPS
# ==========================
INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_yasg",
    "channels",
    # custom apps
    "patients.apps.PatientsConfig",
    "authentication",
    "applications",
    "services",
    "consultations",
    "reviews.apps.ReviewsConfig",
    "core.apps.CoreConfig",
    "partners",
]

# ==========================
# ⚙️ MIDDLEWARE
# ==========================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

# ==========================
# 🧩 TEMPLATES
# ==========================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ==========================
# 🚀 ASGI / CHANNELS
# ==========================
ASGI_APPLICATION = "config.asgi.application"
WSGI_APPLICATION = "config.wsgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
        },
    },
}

# ==========================
# 🧠 AUTH / USERS
# ==========================
AUTH_USER_MODEL = "authentication.CustomUser"

# ==========================
# 💾 DATABASE - LOCAL VA PRODUCTION
# ==========================
    # Production database (Render)
DATABASE_URL = "postgresql://medmapp_db_user:bSHiwNcJcL8206Mby5kMdRp8cF0TPCEF@dpg-d3l05vqdbo4c73egnfs0-a.oregon-postgres.render.com:5432/medmapp_db"
DATABASES = {
    "default": dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=600,
        ssl_require=True
    )
}
# else:
#     # Local database (SQLite yoki PostgreSQL)
#     # VARIANT A: SQLite (oson)
#     DATABASES = {
#         'default': {
#             'ENGINE': 'django.db.backends.sqlite3',
#             'NAME': BASE_DIR / 'db.sqlite3',
#         }
#     }

    # VARIANT B: Local PostgreSQL (agar o'rnatilgan bo'lsa)
    # DATABASES = {
    #     'default': {
    #         'ENGINE': 'django.db.backends.postgresql',
    #         'NAME': 'medmapp_local',
    #         'USER': 'postgres',
    #         'PASSWORD': 'postgres',
    #         'HOST': 'localhost',
    #         'PORT': '5432',
    #     }
    # }

# ==========================
# 🔐 JWT AUTH
# ==========================
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": "your-secret-key",
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ==========================
# 🌐 CORS / CSRF CONFIG
# ==========================
if IS_PRODUCTION:
    CORS_ALLOWED_ORIGINS = [
        "https://med-mapp-admin.vercel.app",
    ]
else:
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

CORS_ALLOW_HEADERS = [
    "content-type",
    "authorization",
]

CSRF_TRUSTED_ORIGINS = [
    "https://medmapp-1pjj.onrender.com",
    "https://med-mapp-admin.vercel.app",
]

# ==========================
# 📄 STATIC / MEDIA
# ==========================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Media papkani yaratish
os.makedirs(MEDIA_ROOT, exist_ok=True)

# ==========================
# 🧭 REST FRAMEWORK
# ==========================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# ==========================
# 📘 SWAGGER
# ==========================
SWAGGER_SETTINGS = {
    "SECURITY_DEFINITIONS": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT tokenini kiriting: **Bearer <token>**",
        }
    },
    "USE_SESSION_AUTH": False,
}
