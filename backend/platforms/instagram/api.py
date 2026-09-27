from typing import TypeVar

from pydantic import BaseModel

from .. import http
from ..http import AUTHENTICATION, AUTHORIZATION, PLATFORM, RATE_LIMIT, PlatformFailure, classify, parse
from .responses import ErrorAnswer, GraphError

LABEL = "Instagram"
GRAPH_VERSION = "v25.0"
GRAPH_ROOT = f"https://graph.facebook.com/{GRAPH_VERSION}"
RUPLOAD_ROOT = f"https://rupload.facebook.com/ig-api-upload/{GRAPH_VERSION}"

TOKEN_REJECTED_CODES = (102, 190)
PERMISSION_CODES = (10, *range(200, 300))
THROTTLED_CODES = (4, 17, 32, 613)

M = TypeVar("M", bound=BaseModel)


def _graph_error(response) -> GraphError | None:
    try:
        return parse(response, ErrorAnswer, label=LABEL).graph_error
    except PlatformFailure:
        return None


def _kind_of(code: int | None, fallback: PlatformFailure | None) -> tuple[str, bool]:
    if code in TOKEN_REJECTED_CODES:
        return AUTHENTICATION, False
    if code in PERMISSION_CODES:
        return AUTHORIZATION, False
    if code in THROTTLED_CODES:
        return RATE_LIMIT, False
    if fallback is not None:
        return fallback.type, fallback.retryable
    return PLATFORM, False


def failure_of(response) -> PlatformFailure | None:
    failure = classify(response, LABEL)
    error = _graph_error(response)
    if failure is None and error is None:
        return None

    error = error or GraphError()
    kind, retryable = _kind_of(error.code, failure)
    message = error.error_user_msg or error.message
    if not message:
        message = failure.message if failure is not None else "Instagram refused the request"
    return PlatformFailure(kind, message[:500], details=error.details, retryable=retryable)


def send(method: str, url: str, *, attempts: int | None = None, **kwargs):
    return http.send(method, url, label=LABEL, failure_of=failure_of, attempts=attempts, **kwargs)


def authorization(access_token: str) -> dict:
    return {"Authorization": f"OAuth {access_token}"}


def call(
    method: str,
    path: str,
    access_token: str,
    model: type[M],
    *,
    refusal: str | None = None,
    attempts: int | None = None,
    **kwargs,
) -> M:
    headers = {**authorization(access_token), **kwargs.pop("headers", {})}
    response = send(method, f"{GRAPH_ROOT}/{path}", attempts=attempts, headers=headers, **kwargs)
    return parse(response, model, label=LABEL, refusal=refusal)
