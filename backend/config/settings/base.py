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

# Project root (the directory containing manage.py).
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load backend/.env if it exists. Real environment variables always win, so a
# container or a CI job can override any of it without editing a file.
load_dotenv(BASE_DIR / ".env", override=False)


def env_bool(name, default=False):
    """Read a boolean env var: "1", "true", "yes" and "on" (any case) mean True."""
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    """Read a comma-separated env var as a list, skipping empty items."""
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# --- Core ---

# Never enable in production: debug pages expose settings and stack traces.
DEBUG = env_bool("DJANGO_DEBUG", False)

# Used by Django for signing. In debug mode a fixed dev key is allowed so the server
# starts without extra setup; in production the env var is mandatory.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or ("dev-insecure-key" if DEBUG else None)
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off")

# Origin the browser uses, scheme included. OAuth redirect URIs are built from it.
# Locally it is the Vite dev server, which proxies /api to this process, so the
# redirect lands on the same origin as the SPA.
PUBLIC_ORIGIN = os.environ.get("PUBLIC_ORIGIN", "http://localhost:5173").rstrip("/")

# Host name only. Still used by the legacy broker endpoints, which build their
# redirect URI as https://<PUBLIC_HOST>/api/social/auth_<provider>/callback.
PUBLIC_HOST = os.environ.get("PUBLIC_HOST", "localhost")

# The SPA is served from PUBLIC_ORIGIN and posts back to this process, so its
# origin has to be trusted for CSRF.
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", PUBLIC_ORIGIN)

# Host names this server answers to. Requests with any other Host header are rejected
# with 400. Defaults to the public host plus local addresses.
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", f"{PUBLIC_HOST},localhost,127.0.0.1")

# The admin is installed but never published: accounts are created through it over
# an SSH tunnel, so it is not routed by any public server config.
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admin",
    "accounts",
    "social",
]

# The API is called by a signed-in browser on the same origin, so sessions, auth and
# CSRF all apply. The only view still exempt from CSRF is the OAuth callback, which
# is a GET the provider redirects to and which defends itself with `state`.
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

# Templates are loaded from each app's templates/ directory (the callback result page
# and the admin). The context processors are the ones the admin needs.
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

# The server runs under uvicorn (ASGI) so the async /poll view can hold long-poll
# connections without tying up a thread each.
ASGI_APPLICATION = "config.asgi.application"

# --- Database ---

# SQLite is the default. The web process, the Celery worker and the embedded beat
# all write to the same file, which works only with the PRAGMAs below:
#   - WAL lets readers run while one writer holds the write lock;
#   - busy_timeout makes a blocked writer wait instead of raising "database is locked";
#   - IMMEDIATE takes the write lock when the transaction opens, so a read that later
#     turns into a write cannot fail halfway through.
# Two rules follow from this and are not optional: never hold a transaction open
# across a network call, and never poll a row in a tight loop.
#
# Set DATABASE_ENGINE=postgresql when "database is locked" starts showing up in the
# worker log; that also requires installing psycopg.
if os.environ.get("DATABASE_ENGINE") == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "oauth_broker"),
            "USER": os.environ.get("POSTGRES_USER", ""),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
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

# Redis, because the web process and the worker must share the rate-limit counters
# and the session cache. It is also the Celery broker, so nothing new is introduced.
REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL},
}

# --- Authentication ---

AUTH_USER_MODEL = "accounts.User"

# Argon2 first: it is the slowest to attack of the hashers Django ships.
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

# Sessions live in the database, read through the Redis cache. Fourteen days,
# refreshed on every request, so an active person is not signed out mid-upload.
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_COOKIE_AGE = 14 * 24 * 60 * 60
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
# The SPA reads this cookie and echoes it in the X-CSRFToken header, so it is not HttpOnly.
CSRF_COOKIE_HTTPONLY = False

# --- Token encryption ---

# Newest key first; see common/fields.py for the format and the rotation procedure.
TOKEN_ENCRYPTION_KEYS = env_list("TOKEN_ENCRYPTION_KEYS")
if not TOKEN_ENCRYPTION_KEYS:
    # Refuse to start rather than fail later: without a key no platform account
    # can be stored, and a key invented at startup would make every row written
    # with it unreadable after a restart.
    raise RuntimeError(
        "TOKEN_ENCRYPTION_KEYS must be set. Generate one with: python -c "
        "\"from cryptography.fernet import Fernet; "
        "print('v1:' + Fernet.generate_key().decode())\""
    )

# --- Limits ---

# Change these here rather than in the code that enforces them. They are the
# defaults for a new user's Quota row and the sizing of the upload protocol.

# Largest single video accepted from the browser.
MAX_MEDIA_ASSET_BYTES = 4 * 1024**3
# Total bytes of stored media one user may hold at a time.
MAX_STORAGE_BYTES = 10 * 1024**3
# How long a media file is kept after every target of its publication finished.
MEDIA_RETENTION_HOURS = 48
# An asset that never got published is swept after this long.
ORPHAN_ASSET_TTL_HOURS = 48
# An upload session with no activity is abandoned after this long.
UPLOAD_SESSION_TTL_HOURS = 6

# Chunk size the server asks the browser to use. Server-chosen so it can be tuned
# without releasing a new frontend.
UPLOAD_CHUNK_BYTES = 8 * 1024**2
# Chunk size used when the worker streams the file on to the platform.
PLATFORM_CHUNK_BYTES = 8 * 1024**2
# Attempts for one chunk before the upload is failed, with exponential backoff.
UPLOAD_RETRY_ATTEMPTS = 5

# Uploads running at once, per worker. Also the default per-user limit.
MAX_CONCURRENT_UPLOADS = 2
# Publications one user may start per day. Exists because the YouTube Data API
# allows about six videos.insert calls a day on the default quota.
MAX_PUBLICATIONS_PER_DAY = 5

# Shortest interval between two progress writes for one target, in seconds.
# The upload loop reports progress far more often than that.
PROGRESS_WRITE_INTERVAL = 1.0

# --- Localization ---

# The only user-facing text is the Russian callback page; no translations are used.
LANGUAGE_CODE = "ru"
TIME_ZONE = "UTC"
USE_I18N = False
# Store timezone-aware datetimes (UTC); session TTL checks rely on this.
USE_TZ = True

# --- Reverse proxy / HTTPS ---

# Host nginx terminates TLS and proxies plain HTTP to uvicorn in Docker. This header tells Django
# the original request was HTTPS, so request.is_secure() is correct.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Cookies are not used by the broker; kept secure in case that changes.
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# --- Logging ---

# Everything goes to stdout/stderr (collected by Docker: `docker compose logs`). Log messages never
# include tokens, codes or the app secret; only session ids and outcomes.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        # Own handler without propagation, otherwise every Django message is printed twice.
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        # urllib3 logs full request URLs at DEBUG; the token exchange URL carries client_secret.
        "urllib3": {"level": "WARNING"},
    },
}

# --- Platforms ---

# Google Cloud console, OAuth client of type "Web application", YouTube Data API
# v3 enabled. The secret only ever comes from the environment and is never logged,
# returned in a response, or compiled into the frontend bundle.
YOUTUBE_CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")

# --- OAuth ---

# How long the person has to finish the consent screen, in seconds. After that
# the callback is refused and the row is swept on the next attempt.
OAUTH_SESSION_TTL = 600

# Timeout for server-to-platform calls, in seconds.
HTTP_TIMEOUT = 10

# Per-client-IP limits as (max requests, window in seconds). Exceeding them returns 429.
# /start is strict because each call creates a DB row; /poll is looser because clients
# repeat it continuously while waiting.
RATE_LIMITS = {
    "login": (10, 300),
    "connect": (20, 300),
    "uploads": (60, 60),
    "publications": (30, 60),
}
# Take the client IP from the rightmost X-Forwarded-For entry (the one a proxy adds).
# Off by default because the server is reached directly while it runs locally, and a
# client that can set the header would otherwise get a fresh rate-limit bucket per
# request. Turn it on only when uvicorn is reachable solely through a proxy.
TRUST_X_FORWARDED_FOR = env_bool("TRUST_X_FORWARDED_FOR", False)
