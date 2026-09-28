import requests

from ..errors import FailureType, PlatformError


class Transport:
    def __init__(self, timeout: float):
        self._timeout = timeout

    def request(self, method: str, url: str, *, label: str, **kwargs):
        kwargs.setdefault("timeout", self._timeout)
        try:
            return requests.request(method, url, **kwargs)
        except requests.RequestException as exc:
            raise PlatformError(
                FailureType.NETWORK, f"{label} request failed: {type(exc).__name__}", retryable=True
            ) from None
