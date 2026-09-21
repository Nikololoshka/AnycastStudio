"""Minimal fixed-window per-IP rate limiting backed by the Django cache.

With LocMemCache the counters are per worker process; use a shared cache (e.g. Redis)
or limit in the reverse proxy when running several workers.
"""

import time

from django.conf import settings
from django.core.cache import cache


def client_ip(request) -> str:
    if settings.TRUST_X_FORWARDED_FOR:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            # The proxy appends the real peer address, so the rightmost entry is trustworthy.
            return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "")


def is_rate_limited(request, scope: str) -> bool:
    limit, window = settings.RATE_LIMITS[scope]
    bucket = int(time.time() // window)
    key = f"rl:{scope}:{client_ip(request)}:{bucket}"
    cache.add(key, 0, timeout=window + 1)
    try:
        count = cache.incr(key)
    except ValueError:  # evicted between add and incr
        cache.set(key, 1, timeout=window + 1)
        count = 1
    return count > limit
