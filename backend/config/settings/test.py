"""Settings for the test suite. No network, no disk, fast timings."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key")
os.environ.setdefault("TOKEN_ENCRYPTION_KEYS", "v1:0OCGKlCLB8oeiYM9wmmDs9vjshMpdvlPrN3n-9Gc_Rk=")

from .base import *  # noqa: E402,F401,F403

PUBLIC_ORIGIN = "http://testserver"
ALLOWED_HOSTS = ["testserver"]

YOUTUBE_CLIENT_ID = "test-client-id"
YOUTUBE_CLIENT_SECRET = "test-client-secret-DO-NOT-LEAK"

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

# No Redis in tests. Each test case clears the cache, so per-process counters are enough.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# Hashing a password with Argon2 dominates the runtime of an authentication test.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

LOGGING = {**LOGGING, "root": {"handlers": ["console"], "level": "CRITICAL"}}  # noqa: F405
