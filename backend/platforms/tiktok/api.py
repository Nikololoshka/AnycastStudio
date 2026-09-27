from ..http import AUTHENTICATION, PLATFORM, PlatformFailure, classify, json_dict, request, with_retry

LABEL = "TikTok"
API_ROOT = "https://open.tiktokapis.com/v2"

OK_CODE = "ok"
TOKEN_REJECTED_CODES = ("access_token_invalid", "scope_not_authorized")


def error_code(response) -> str:
    error = json_dict(response).get("error")
    return str(error.get("code") or "") if isinstance(error, dict) else ""


def _attempt(method: str, url: str, kwargs: dict):
    response = request(method, url, label=LABEL, **kwargs)
    failure = classify(response, LABEL)
    if failure is not None:
        failure.details = error_code(response)
        raise failure
    return response


def send(method: str, url: str, *, attempts: int | None = None, **kwargs):
    return with_retry(lambda: _attempt(method, url, kwargs), label=LABEL, attempts=attempts)


def bearer(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"}


def data_of(response) -> dict:
    body = json_dict(response)
    error = body.get("error") if isinstance(body.get("error"), dict) else {}
    code = str(error.get("code") or OK_CODE)
    if code != OK_CODE:
        kind = AUTHENTICATION if code in TOKEN_REJECTED_CODES else PLATFORM
        raise PlatformFailure(kind, str(error.get("message") or f"TikTok answered {code}")[:500], details=code)
    data = body.get("data")
    return data if isinstance(data, dict) else {}


def call(method: str, url: str, access_token: str, **kwargs) -> dict:
    return data_of(send(method, url, headers=bearer(access_token), **kwargs))
