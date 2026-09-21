"""Local development settings."""

import os

os.environ.setdefault("DJANGO_DEBUG", "1")

from .base import *  # noqa: E402,F401,F403
