from typing import TypeVar

from pydantic import BaseModel

from .. import http
from ..http import AUTHORIZATION, RATE_LIMIT, PlatformFailure, classify, parse
from .responses import Data, Problem, ProblemAnswer

LABEL = "X"
API_ROOT = "https://api.x.com/2"

USAGE_CAPPED = "usage-capped"
CLIENT_FORBIDDEN = "client-forbidden"

M = TypeVar("M", bound=BaseModel)


def _problem_of(response) -> Problem:
    try:
        return parse(response, ProblemAnswer, label=LABEL).problem
    except PlatformFailure:
        return Problem()


def failure_of(response) -> PlatformFailure | None:
    failure = classify(response, LABEL)
    if failure is None:
        return None

    problem = _problem_of(response)
    kind = problem.kind
    message = (problem.text or failure.message)[:500]

    if kind == USAGE_CAPPED:
        return PlatformFailure(RATE_LIMIT, message, details=kind)
    if kind == CLIENT_FORBIDDEN:
        return PlatformFailure(AUTHORIZATION, message, details=kind)
    return PlatformFailure(failure.type, message, details=kind, retryable=failure.retryable)


def send(method: str, url: str, *, attempts: int | None = None, **kwargs):
    return http.send(method, url, label=LABEL, failure_of=failure_of, attempts=attempts, **kwargs)


def bearer(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


def call(method: str, path: str, access_token: str, *, attempts: int | None = None, **kwargs):
    headers = {**bearer(access_token), **kwargs.pop("headers", {})}
    return send(method, f"{API_ROOT}/{path}", attempts=attempts, headers=headers, **kwargs)


def data_of(response, model: type[M], *, refusal: str | None = None) -> M:
    return parse(response, Data[model], label=LABEL, refusal=refusal).data
