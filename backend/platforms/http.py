"""Shared HTTP behaviour for platform calls.

Kept apart from any one platform because every platform needs the same thing:
a timeout, a JSON body that may not be JSON, and an error that never carries
the request URL — which is where client secrets live.
"""

import requests
from django.conf import settings

from .base import ProviderError


def json_dict(response) -> dict:
    try:
        data = response.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def request(method: str, url: str, *, label: str, **kwargs):
    kwargs.setdefault("timeout", settings.HTTP_TIMEOUT)
    try:
        return requests.request(method, url, **kwargs)
    except requests.RequestException as exc:
        # The exception text can contain the request URL, and the token endpoint
        # carries client_secret in its body. Report the class, never the detail.
        raise ProviderError(f"{label} request failed: {type(exc).__name__}") from None
