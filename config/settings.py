# ===============================================================
# DJANGO SETTINGS – MEDMAPP (FINAL PRODUCTION VERSION)
# ===============================================================

import os
from pathlib import Path
from datetime import timedelta
import dj_database_url
from django.utils.translation import gettext_lazy as _

# ===============================================================
# BASE
# ===============================================================
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "change-me-in-production")

ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT == "production"

DEBUG = os.environ.get("DEBUG", "False").lower() == "true"

# ===============================================================
# HOSTS
# ===============================================================
ALLOWED_HOSTS = [
    "admin.medmapp.uz",
    "medmapp-1pjj.onrender.com",
    "med-mapp-admin.vercel.app",
    "med-mapp-one.vercel.app",
    "176.96.243.144",
    "localhost",
    "127.0.0.1",
    ".vercel.app",
]

# ===============================================================
# LANGUAGE & TIME
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

LOCALE_PATHS = [BASE_DIR / "locale"]

# ===============================================================
# INSTALLED APPS
# ===============================================================
INSTALLED_APPS = [
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
# MIDDLEWARE
# ===============================================================
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
# TEMPLATES
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

# ===============================================================
# AUTH USER
# ===============================================================
AUTH_USER_MODEL = "authentication.CustomUser"

# ===============================================================
# DATABASE (POSTGRES – DOCKER + RENDER SUPPORT)
# ===============================================================
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://medmapp_db_user:bSHiwNcJcL8206Mby5kMdRp8cF0TPCEF@dpg-d3l05vqdbo4c73egnfs0-a.oregon-postgres.render.com:5432/medmapp_db"
)

DATABASES = {
    "default": dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=600,
        ssl_require=False,   # Docker Postgres uchun MUHIM!
    )
}

# ===============================================================
# HTTPS / REVERSE PROXY FIX
# ===============================================================
# NGINX -> Django uchun to‘g‘ri SSL forwarding
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ===============================================================
# JWT AUTHENTICATION
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
# CORS & CSRF (PERFECT)
# ===============================================================
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGINS = [
    "https://admin.medmapp.uz",
    "http://admin.medmapp.uz",

    "https://med-mapp-admin.vercel.app",
    "https://med-mapp-one.vercel.app",
    "https://medmapp-1pjj.onrender.com",

    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://[\w-]+\.vercel\.app$",
]

CSRF_TRUSTED_ORIGINS = [
    "https://admin.medmapp.uz",
    "http://admin.medmapp.uz",

    "https://*.vercel.app",
    "https://med-mapp-admin.vercel.app",
    "https://med-mapp-one.vercel.app",
    "https://medmapp-1pjj.onrender.com",
]

CORS_ALLOW_HEADERS = ["*"]
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

# ===============================================================
# STATIC / MEDIA
# ===============================================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ===============================================================
# DRF
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

# ===============================================================
# SWAGGER (HTTPS FIX)
# ===============================================================
SWAGGER_SETTINGS = {
    "USE_SESSION_AUTH": False,
    "DEFAULT_API_URL": "https://admin.medmapp.uz",
    "SECURITY_DEFINITIONS": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
        }
    },
}

# ===============================================================
# SECURITY
# ===============================================================
if IS_PRODUCTION:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0

# ===============================================================
# LOGGING
# ===============================================================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
