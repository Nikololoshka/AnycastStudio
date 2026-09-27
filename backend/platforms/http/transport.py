import requests
from django.conf import settings

from .failures import NETWORK, PlatformFailure


def request(method: str, url: str, *, label: str, **kwargs):
    kwargs.setdefault("timeout", settings.HTTP_TIMEOUT)
    try:
        return requests.request(method, url, **kwargs)
    except requests.RequestException as exc:
        raise PlatformFailure(NETWORK, f"{label} request failed: {type(exc).__name__}", retryable=True) from None
