"""Shared HTTP behaviour for platform calls.

Kept apart from any one platform because every platform needs the same thing: a
timeout, a JSON body that may not be JSON, an error that never carries the
request URL — which is where client secrets live — and a retry policy.

The retry policy is a port of the one the desktop client proved in Rust: five
attempts, exponential backoff from one second to thirty with jitter, and a
sharp line between what is worth repeating and what is not. Repeating a
rejected upload wastes quota the person cannot get back.
"""

import logging
import random
import time
from dataclasses import dataclass

import requests
from django.conf import settings

from .base import ProviderError

logger = logging.getLogger(__name__)

BASE_BACKOFF_MS = 1_000
MAX_BACKOFF_MS = 30_000

# The vocabulary the frontend already speaks; see domain/publication/types.ts.
NETWORK = "network"
AUTHENTICATION = "authentication"
AUTHORIZATION = "authorization"
RATE_LIMIT = "rate_limit"
PLATFORM = "platform"
VALIDATION = "validation"
UNKNOWN = "unknown"


@dataclass(eq=False)  # keep Exception hashable
class PlatformFailure(Exception):
    """A platform call that failed, classified so the person sees the right thing."""

    type: str
    message: str
    details: str = ""
    retryable: bool = False

    def __str__(self) -> str:
        return self.message


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


def message_of(response, label: str) -> str:
    body = json_dict(response)
    error = body.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error.get("status") or "")[:500]
    if isinstance(error, str):
        return error[:500]
    return f"{label} answered HTTP {response.status_code}"


def classify(response, label: str) -> PlatformFailure | None:
    """Decide what a response means. None means it succeeded.

    408 and 429 and the 5xx range are the platform's problem and are worth
    repeating. 401 means the token has to be refreshed first, which is the
    caller's job. 403 is a decision — a revoked scope, an exhausted quota — and
    repeating it only burns more.
    """
    status = response.status_code

    if 200 <= status < 300 or status == 308:
        return None

    message = message_of(response, label)

    # Not retryable: repeating the same expired token changes nothing. The
    # caller refreshes it and resumes from where it stopped.
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


def backoff_ms(attempt: int) -> int:
    """Exponential, capped, with jitter so retries do not arrive in lockstep."""
    ceiling = min(BASE_BACKOFF_MS * (2**attempt), MAX_BACKOFF_MS)
    return random.randint(ceiling // 2, ceiling)


def with_retry(send, *, label: str, attempts: int | None = None, sleep=time.sleep):
    """Call `send()` until it returns a usable response or the attempts run out.

    `send` returns a response. Anything it raises that is not a ProviderError
    propagates: a bug should not be retried five times.
    """
    attempts = attempts or settings.UPLOAD_RETRY_ATTEMPTS
    last: PlatformFailure | None = None

    for attempt in range(attempts):
        try:
            response = send()
        except ProviderError as error:
            last = PlatformFailure(NETWORK, error.message, retryable=True)
        else:
            failure = classify(response, label)
            if failure is None:
                return response
            last = failure

        if not last.retryable or attempt == attempts - 1:
            raise last

        delay = backoff_ms(attempt)
        logger.info("%s: %s, retrying in %d ms", label, last.message, delay)
        sleep(delay / 1000)

    raise last
