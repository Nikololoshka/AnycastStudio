from dataclasses import dataclass

from .body import message_of

NETWORK = "network"
AUTHENTICATION = "authentication"
AUTHORIZATION = "authorization"
RATE_LIMIT = "rate_limit"
PLATFORM = "platform"
VALIDATION = "validation"
FILE = "file"
UNKNOWN = "unknown"


@dataclass(eq=False)
class PlatformFailure(Exception):
    type: str
    message: str
    details: str = ""
    retryable: bool = False

    def __str__(self) -> str:
        return self.message


def classify(response, label: str) -> PlatformFailure | None:
    status = response.status_code

    if 200 <= status < 300 or status == 308:
        return None

    message = message_of(response, label)

    if status == 401:
        return PlatformFailure(AUTHENTICATION, message or "The connection expired")
    if status == 403:
        return PlatformFailure(AUTHORIZATION, message or "The platform refused")
    if status == 429:
        return PlatformFailure(RATE_LIMIT, message or "Too many requests", retryable=True)
    if status in (400, 404, 409, 422):
        return PlatformFailure(VALIDATION, message or "The platform rejected the request")
    if status >= 500 or status == 408:
        return PlatformFailure(PLATFORM, message or "The platform is unavailable", retryable=True)

    return PlatformFailure(PLATFORM, message)
