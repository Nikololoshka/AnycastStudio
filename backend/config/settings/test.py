"""Settings for the test suite. No network, no disk, fast timings."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key")
os.environ.setdefault("CLIENT_TOKENS", "test-client-token")

from .base import *  # noqa: E402,F401,F403

FB_APP_ID = "test-app-id"
FB_APP_SECRET = "test-app-secret-DO-NOT-LEAK"
FB_GRAPH_VERSION = "v23.0"
PUBLIC_HOST = "auth.test"
ALLOWED_HOSTS = ["testserver"]

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

# No Redis in tests. Each test case clears the cache, so per-process counters are enough.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

TOKEN_ENCRYPTION_KEYS = ["v1:0OCGKlCLB8oeiYM9wmmDs9vjshMpdvlPrN3n-9Gc_Rk="]

# Hashing a password with Argon2 dominates the runtime of an authentication test.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

POLL_TIMEOUT = 0.3
POLL_INTERVAL = 0.05

LOGGING = {**LOGGING, "root": {"handlers": ["console"], "level": "CRITICAL"}}  # noqa: F405
