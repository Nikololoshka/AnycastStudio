from ..http import (
    AUTHORIZATION,
    RATE_LIMIT,
    PlatformFailure,
    classify,
    json_dict,
    request,
    with_retry,
)

LABEL = "X"
API_ROOT = "https://api.x.com/2"
PROBLEM_PREFIX = "https://api.x.com/2/problems/"

USAGE_CAPPED = "usage-capped"
CLIENT_FORBIDDEN = "client-forbidden"


def _problem_of(body: dict) -> dict:
    if body.get("type") or body.get("detail") or body.get("title"):
        return body
    errors = body.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], dict) and not body.get("data"):
        return errors[0]
    return {}


def problem_kind(problem: dict) -> str:
    kind = str(problem.get("type") or "")
    return kind.removeprefix(PROBLEM_PREFIX)


def failure_of(response) -> PlatformFailure | None:
    failure = classify(response, LABEL)
    if failure is None:
        return None

    problem = _problem_of(json_dict(response))
    kind = problem_kind(problem)
    message = problem.get("detail") or problem.get("title") or problem.get("message") or failure.message

    if kind == USAGE_CAPPED:
        return PlatformFailure(RATE_LIMIT, str(message)[:500], details=kind)
    if kind == CLIENT_FORBIDDEN:
        return PlatformFailure(AUTHORIZATION, str(message)[:500], details=kind)
    return PlatformFailure(failure.type, str(message)[:500], details=kind, retryable=failure.retryable)


def _attempt(method: str, url: str, kwargs: dict):
    response = request(method, url, label=LABEL, **kwargs)
    failure = failure_of(response)
    if failure is not None:
        raise failure
    return response


def send(method: str, url: str, *, attempts: int | None = None, **kwargs):
    return with_retry(lambda: _attempt(method, url, kwargs), label=LABEL, attempts=attempts)


def bearer(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


def call(method: str, path: str, access_token: str, *, attempts: int | None = None, **kwargs) -> dict:
    headers = {**bearer(access_token), **kwargs.pop("headers", {})}
    return json_dict(send(method, f"{API_ROOT}/{path}", attempts=attempts, headers=headers, **kwargs))


def data_of(body: dict) -> dict:
    data = body.get("data")
    return data if isinstance(data, dict) else {}

