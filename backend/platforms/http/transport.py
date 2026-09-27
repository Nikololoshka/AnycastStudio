import requests
from django.conf import settings

from .failures import NETWORK, PlatformFailure, classify
from .retry import with_retry


def request(method: str, url: str, *, label: str, **kwargs):
    kwargs.setdefault("timeout", settings.HTTP_TIMEOUT)
    try:
        return requests.request(method, url, **kwargs)
    except requests.RequestException as exc:
        raise PlatformFailure(NETWORK, f"{label} request failed: {type(exc).__name__}", retryable=True) from None


def send(method: str, url: str, *, label: str, failure_of=None, attempts: int | None = None, **kwargs):
    def attempt():
        response = request(method, url, label=label, **kwargs)
        failure = failure_of(response) if failure_of else classify(response, label)
        if failure is not None:
            raise failure
        return response

    return with_retry(attempt, label=label, attempts=attempts)
