from .. import http
from ..http import (
    AUTHENTICATION,
    AUTHORIZATION,
    PLATFORM,
    RATE_LIMIT,
    PlatformFailure,
    classify,
    json_dict,
)

LABEL = "Instagram"
GRAPH_VERSION = "v25.0"
GRAPH_ROOT = f"https://graph.facebook.com/{GRAPH_VERSION}"
RUPLOAD_ROOT = f"https://rupload.facebook.com/ig-api-upload/{GRAPH_VERSION}"

TOKEN_REJECTED_CODES = (102, 190)
PERMISSION_CODES = (10, *range(200, 300))
THROTTLED_CODES = (4, 17, 32, 613)


def _error_of(body: dict) -> dict:
    for key in ("error", "debug_info"):
        if isinstance(body.get(key), dict):
            return body[key]
    return {}


def error_code(error: dict) -> str:
    code = str(error.get("code") or "")
    subcode = str(error.get("error_subcode") or "")
    return f"{code}/{subcode}" if code and subcode else code


def _kind_of(code, fallback: PlatformFailure | None) -> tuple[str, bool]:
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
    error = _error_of(json_dict(response))
    if failure is None and not error:
        return None

    kind, retryable = _kind_of(error.get("code"), failure)
    message = error.get("error_user_msg") or error.get("message")
    if not message:
        message = failure.message if failure is not None else "Instagram refused the request"
    return PlatformFailure(kind, str(message)[:500], details=error_code(error), retryable=retryable)


def send(method: str, url: str, *, attempts: int | None = None, **kwargs):
    return http.send(method, url, label=LABEL, failure_of=failure_of, attempts=attempts, **kwargs)


def authorization(access_token: str) -> dict:
    return {"Authorization": f"OAuth {access_token}"}


def call(method: str, path: str, access_token: str, *, attempts: int | None = None, **kwargs) -> dict:
    headers = {**authorization(access_token), **kwargs.pop("headers", {})}
    return json_dict(send(method, f"{GRAPH_ROOT}/{path}", attempts=attempts, headers=headers, **kwargs))
