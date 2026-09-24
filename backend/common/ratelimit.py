import time

from django.conf import settings
from django.core.cache import cache


def _address_appended_by_proxy(forwarded: str) -> str:
    return forwarded.split(",")[-1].strip()


def client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if settings.TRUST_X_FORWARDED_FOR and forwarded:
        return _address_appended_by_proxy(forwarded)
    return request.META.get("REMOTE_ADDR", "")


def _count_hit(key: str, window: int) -> int:
    cache.add(key, 0, timeout=window + 1)
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window + 1)
        return 1


def is_rate_limited(request, scope: str) -> bool:
    limit, window = settings.RATE_LIMITS[scope]
    bucket = int(time.time() // window)
    return _count_hit(f"rl:{scope}:{client_ip(request)}:{bucket}", window) > limit
