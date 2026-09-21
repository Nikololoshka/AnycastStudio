"""
Settings shared by every environment.

Secrets and deployment-specific values come from environment variables
(see .env.example). Nothing secret is hard-coded here.

config/settings/dev.py and config/settings/test.py import this module and
override what differs. Select one with DJANGO_SETTINGS_MODULE.
"""

import os
from pathlib import Path

# Project root (the directory containing manage.py).
BASE_DIR = Path(__file__).resolve().parent.parent.parent


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

# Public host name of the server, e.g. "auth.example.com". OAuth redirect URIs are built
# from it: https://<PUBLIC_HOST>/api/social/auth_<provider>/callback.
PUBLIC_HOST = os.environ.get("PUBLIC_HOST", "localhost")

# Host names this server answers to. Requests with any other Host header are rejected
# with 400. Defaults to the public host plus local addresses.
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", f"{PUBLIC_HOST},localhost,127.0.0.1")

# Deliberately minimal: no admin, auth, sessions or static files. The broker only
# needs its own app; contenttypes is required by Django's model machinery.
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "social",
]

# No session, CSRF or auth middleware: the API is called by the desktop app, not by
# a logged-in browser. The POST views are marked csrf_exempt explicitly.
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

# Templates are loaded from each app's templates/ directory (the callback result page).
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

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

# Used only for rate-limit counters. LocMemCache is per process, so with several
# workers each one counts separately; switch to a shared cache (e.g. Redis) then.
CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}

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

# --- OAuth broker: Facebook ---

# App ID and App Secret from the Facebook developer console (App settings -> Basic).
# The secret must only ever come from the environment and is never logged or returned.
FB_APP_ID = os.environ.get("FB_APP_ID", "")
FB_APP_SECRET = os.environ.get("FB_APP_SECRET", "")
# Graph API version used for both the login dialog and the token endpoint.
# Update to the current version when Facebook deprecates this one.
FB_GRAPH_VERSION = os.environ.get("FB_GRAPH_VERSION", "v23.0")
# Permissions requested in the login dialog.
FB_SCOPE = "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement"

# --- OAuth broker: common (all providers) ---

# Tokens that allow a client (the desktop app) to call /start, sent as `Authorization: Bearer <token>`.
# Comma-separated, so a token can be rotated by adding the new one before removing the old one.
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
CLIENT_TOKENS = env_list("CLIENT_TOKENS")
if not CLIENT_TOKENS and not DEBUG:
    raise RuntimeError("CLIENT_TOKENS must be set when DJANGO_DEBUG is off")

# How long an auth session lives after /start, in seconds. After that the callback
# is rejected, /poll answers 410, and the row is deleted on the next /start.
AUTH_SESSION_TTL = 600
# How long a single /poll request is held open before answering "pending", in seconds.
# Clients must use a longer HTTP timeout than this.
POLL_TIMEOUT = 25
# How often /poll re-checks the session status while waiting, in seconds.
POLL_INTERVAL = 1
# Timeout for server-to-provider calls (e.g. exchanging the code for a token), in seconds.
HTTP_TIMEOUT = 10

# Per-client-IP limits as (max requests, window in seconds). Exceeding them returns 429.
# /start is strict because each call creates a DB row; /poll is looser because clients
# repeat it continuously while waiting.
RATE_LIMITS = {
    "start": (10, 60),
    "poll": (120, 60),
}
# Take the client IP from the rightmost X-Forwarded-For entry (the one added by nginx).
# Keep enabled only when uvicorn is reachable solely through the proxy; if the server
# is exposed directly, clients could forge the header, so set this to 0.
TRUST_X_FORWARDED_FOR = env_bool("TRUST_X_FORWARDED_FOR", True)
