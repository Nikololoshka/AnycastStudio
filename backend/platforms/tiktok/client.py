from typing import TypeVar

from pydantic import BaseModel

from config.wiring import container

from ..core.errors import FailureType, PlatformError
from ..core.http import FailureClassifier, PlatformClient, ResponseParser
from .responses import Envelope

LABEL = "TikTok"
API_ROOT = "https://open.tiktokapis.com/v2"

TOKEN_REJECTED_CODES = ("access_token_invalid", "scope_not_authorized")

M = TypeVar("M", bound=BaseModel)


class TikTokFailureClassifier(FailureClassifier):
    def classify(self, response, label: str) -> PlatformError | None:
        failure = super().classify(response, label)
        if failure is not None:
            try:
                failure.details = ResponseParser(label).parse(response, Envelope).error.code
            except PlatformError:
                failure.details = ""
        return failure


class TikTokClient(PlatformClient):
    label = LABEL

    def __init__(self, config):
        super().__init__(config, TikTokFailureClassifier())

    @staticmethod
    def bearer(access_token: str) -> dict:
        return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"}

    def data_of(self, response, model: type[M], *, refusal: str | None = None) -> M:
        envelope = self.parse(response, Envelope)
        error = envelope.error
        if error.refused:
            kind = FailureType.AUTHENTICATION if error.code in TOKEN_REJECTED_CODES else FailureType.PLATFORM
            raise PlatformError(kind, (error.message or f"TikTok answered {error.code}")[:500], details=error.code)
        return self.parse_body(envelope.data, model, refusal=refusal)

    def call(self, method: str, url: str, access_token: str, model: type[M], *, refusal: str | None = None, **kwargs) -> M:
        return self.data_of(self.send(method, url, headers=self.bearer(access_token), **kwargs), model, refusal=refusal)


def client() -> TikTokClient:
    return TikTokClient(container().config.http)


def send(method: str, url: str, *, attempts: int | None = None, **kwargs):
    return client().send(method, url, attempts=attempts, **kwargs)


def data_of(response, model: type[M], *, refusal: str | None = None) -> M:
    return client().data_of(response, model, refusal=refusal)


def call(method: str, url: str, access_token: str, model: type[M], *, refusal: str | None = None, **kwargs) -> M:
    return client().call(method, url, access_token, model, refusal=refusal, **kwargs)
