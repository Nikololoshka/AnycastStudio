from typing import TypeVar

from pydantic import BaseModel

from .. import http
from ..http import AUTHENTICATION, PLATFORM, PlatformFailure, classify, parse, parse_body
from .responses import Envelope

LABEL = "TikTok"
API_ROOT = "https://open.tiktokapis.com/v2"

TOKEN_REJECTED_CODES = ("access_token_invalid", "scope_not_authorized")

M = TypeVar("M", bound=BaseModel)


def _envelope(response) -> Envelope:
    return parse(response, Envelope, label=LABEL)


def failure_of(response) -> PlatformFailure | None:
    failure = classify(response, LABEL)
    if failure is not None:
        try:
            failure.details = _envelope(response).error.code
        except PlatformFailure:
            failure.details = ""
    return failure


def send(method: str, url: str, *, attempts: int | None = None, **kwargs):
    return http.send(method, url, label=LABEL, failure_of=failure_of, attempts=attempts, **kwargs)


def bearer(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"}


def data_of(response, model: type[M], *, refusal: str | None = None) -> M:
    envelope = _envelope(response)
    error = envelope.error
    if error.refused:
        kind = AUTHENTICATION if error.code in TOKEN_REJECTED_CODES else PLATFORM
        raise PlatformFailure(kind, (error.message or f"TikTok answered {error.code}")[:500], details=error.code)
    return parse_body(envelope.data, model, label=LABEL, refusal=refusal)


def call(method: str, url: str, access_token: str, model: type[M], *, refusal: str | None = None, **kwargs) -> M:
    return data_of(send(method, url, headers=bearer(access_token), **kwargs), model, refusal=refusal)
