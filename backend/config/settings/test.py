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

POLL_TIMEOUT = 0.3
POLL_INTERVAL = 0.05

LOGGING = {**LOGGING, "root": {"handlers": ["console"], "level": "CRITICAL"}}  # noqa: F405
