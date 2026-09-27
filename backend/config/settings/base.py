"""
Settings shared by every environment.

Secrets and deployment-specific values come from environment variables
(see .env.example). Nothing secret is hard-coded here.

config/settings/dev.py and config/settings/test.py import this module and
override what differs. Select one with DJANGO_SETTINGS_MODULE.
"""

import os
from pathlib import Path

from dotenv import load_dotenv


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}

def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]

# --- Core ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env", override=False)
DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or ("dev-insecure-key" if DEBUG else None)
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off")

PUBLIC_ORIGIN = os.environ.get("PUBLIC_ORIGIN", "http://localhost:5173").rstrip("/")
PUBLIC_HOST = os.environ.get("PUBLIC_HOST", "localhost")

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", PUBLIC_ORIGIN)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", f"{PUBLIC_HOST}, localhost, 127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admin",
    "accounts",
    "media",
    "publishing",
    "social",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.request",
            ]
        },
    },
]

STATIC_URL = "static/"

MEDIA_ROOT = os.environ.get("MEDIA_ROOT", str(BASE_DIR / "media_files"))

DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024

ASGI_APPLICATION = "config.asgi.application"

# --- Database ---
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("SQLITE_PATH", BASE_DIR / "db.sqlite3"),
        "OPTIONS": {
            "timeout": 30,
            "transaction_mode": "IMMEDIATE",
            "init_command": (
                "PRAGMA journal_mode=WAL;"
                "PRAGMA synchronous=NORMAL;"
                "PRAGMA busy_timeout=30000;"
            ),
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Cache ---
REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL},
}

# --- Authentication ---
AUTH_USER_MODEL = "accounts.User"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_COOKIE_AGE = 14 * 24 * 60 * 60
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False
CSRF_FAILURE_VIEW = "common.responses.error_views.csrf_failure"

# --- Token encryption ---
TOKEN_ENCRYPTION_KEYS = env_list("TOKEN_ENCRYPTION_KEYS")
if not TOKEN_ENCRYPTION_KEYS:
    raise RuntimeError(
        "TOKEN_ENCRYPTION_KEYS must be set. Generate one with: python -c "
        "\"from cryptography.fernet import Fernet; "
        "print('v1:' + Fernet.generate_key().decode())\""
    )

# --- Background work ---
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = None
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_TRANSPORT_OPTIONS = {"visibility_timeout": 3 * 60 * 60}

CELERY_BEAT_SCHEDULE = {
    "sweep-upload-sessions": {"task": "media.sweep_upload_sessions", "schedule": 900.0},
    "sweep-unused-assets": {"task": "media.sweep_unused_assets", "schedule": 3600.0},
    "refresh-expiring-tokens": {"task": "social.refresh_expiring_tokens", "schedule": 1800.0},
    "dispatch-due-targets": {"task": "publishing.dispatch_due_targets", "schedule": 60.0},
}

CELERY_TASK_ALWAYS_EAGER = False

# --- Limits ---
MAX_MEDIA_ASSET_BYTES = 4 * 1024**3
MAX_STORAGE_BYTES = 10 * 1024**3
MEDIA_RETENTION_HOURS = 48
ORPHAN_ASSET_TTL_HOURS = 48
UPLOAD_SESSION_TTL_HOURS = 6
UPLOAD_CHUNK_BYTES = 8 * 1024**2
PLATFORM_CHUNK_BYTES = 8 * 1024**2
UPLOAD_RETRY_ATTEMPTS = 5
MAX_CONCURRENT_UPLOADS = 2
MAX_PUBLICATIONS_PER_DAY = 5
PROGRESS_WRITE_INTERVAL = 1.0

# --- Localization ---
LANGUAGE_CODE = "ru"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

# --- Reverse proxy / HTTPS ---
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# --- Logging ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "urllib3": {"level": "WARNING"},
    },
}

# --- Platforms ---
YOUTUBE_CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
TIKTOK_CLIENT_KEY = os.environ.get("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET", "")

# --- OAuth ---
OAUTH_SESSION_TTL = 600
HTTP_TIMEOUT = 10

RATE_LIMITS = {
    "login": (10, 300),
    "connect": (20, 300),
    "creator_info": (30, 60),
    "uploads": (60, 60),
    "publications": (30, 60),
}

TRUST_X_FORWARDED_FOR = env_bool("TRUST_X_FORWARDED_FOR", False)
