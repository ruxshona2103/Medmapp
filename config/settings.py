# ===============================================================
# DJANGO SETTINGS – MEDMAPP PROJECT (PRODUCTION READY)
# ===============================================================
import os
from pathlib import Path
from datetime import timedelta
import dj_database_url
from django.utils.translation import gettext_lazy as _

# ===============================================================
# 🔧 BASE SETTINGS
# ===============================================================
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-dev-key")

ENVIRONMENT = os.environ.get("ENVIRONMENT", "production")
IS_PRODUCTION = ENVIRONMENT == "production"
DEBUG = not IS_PRODUCTION

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "medmapp-1pjj.onrender.com",
    "med-mapp-admin.vercel.app",
]

# ===============================================================
# 🌍 LANGUAGE & TIMEZONE
# ===============================================================
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ("uz", _("Uzbek")),
    ("ru", _("Russian")),
    ("en", _("English")),
]

# ===============================================================
# 📦 INSTALLED APPS
# ===============================================================
INSTALLED_APPS = [
    # Core
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_yasg",
    "channels",

    # Custom apps
    "authentication",
    "patients",
    "applications",
    "services",
    "consultations",
    "reviews",
    "core",
    "partners",
]

# ===============================================================
# ⚙️ MIDDLEWARE (CORS eng tepada!)
# ===============================================================
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # 🔥 Birinchi bo‘lishi kerak!
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

# ===============================================================
# 🧩 TEMPLATES
# ===============================================================
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

# ===============================================================
# 🚀 ASGI / CHANNELS
# ===============================================================
ASGI_APPLICATION = "config.asgi.application"
WSGI_APPLICATION = "config.wsgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [("127.0.0.1", 6379)]},
    },
}

# ===============================================================
# 👤 AUTH / USERS
# ===============================================================
AUTH_USER_MODEL = "authentication.CustomUser"

# ===============================================================
# 💾 DATABASE (Render PostgreSQL)
# ===============================================================
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://medmapp_db_user:bSHiwNcJcL8206Mby5kMdRp8cF0TPCEF@dpg-d3l05vqdbo4c73egnfs0-a.oregon-postgres.render.com:5432/medmapp_db"
)

DATABASES = {
    "default": dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=600,
        ssl_require=True,
    )
}

# ===============================================================
# 🔐 JWT AUTHENTICATION
# ===============================================================
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
# 🌐 CORS / CSRF CONFIG
# ===============================================================
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_HEADERS = True

CORS_ALLOWED_ORIGINS = [
    "https://med-mapp-admin.vercel.app",
    "https://medmapp-1pjj.onrender.com",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
]

CSRF_TRUSTED_ORIGINS = [
    "https://med-mapp-admin.vercel.app",
    "https://medmapp-1pjj.onrender.com",
]

CORS_ALLOW_METHODS = [
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "OPTIONS",
]

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

# 🔄 agar boshqa subdomenlar (vercel preview) bo‘lsa
CORS_ALLOWED_ORIGIN_REGEXES = [r"^https://.*\.vercel\.app$"]

# ===============================================================
# 📄 STATIC / MEDIA FILES
# ===============================================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
os.makedirs(MEDIA_ROOT, exist_ok=True)

# ===============================================================
# 🧭 REST FRAMEWORK
# ===============================================================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# ===============================================================
# 📘 SWAGGER SETTINGS
# ===============================================================
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
