from typing import TypeVar

from pydantic import BaseModel

from config.wiring import container

from ..core.errors import FailureType, PlatformError
from ..core.http import FailureClassifier, PlatformClient, ResponseParser
from .responses import ErrorAnswer, GraphError

LABEL = "Instagram"
GRAPH_VERSION = "v25.0"
GRAPH_ROOT = f"https://graph.facebook.com/{GRAPH_VERSION}"
RUPLOAD_ROOT = f"https://rupload.facebook.com/ig-api-upload/{GRAPH_VERSION}"

TOKEN_REJECTED_CODES = (102, 190)
PERMISSION_CODES = (10, *range(200, 300))
THROTTLED_CODES = (4, 17, 32, 613)

M = TypeVar("M", bound=BaseModel)


class InstagramFailureClassifier(FailureClassifier):
    def classify(self, response, label: str) -> PlatformError | None:
        failure = super().classify(response, label)
        error = self._graph_error(response, label)
        if failure is None and error is None:
            return None

        error = error or GraphError()
        kind, retryable = self._kind_of(error.code, failure)
        message = error.error_user_msg or error.message
        if not message:
            message = failure.message if failure is not None else "Instagram refused the request"
        return PlatformError(kind, message[:500], details=error.details, retryable=retryable)

    @staticmethod
    def _graph_error(response, label: str) -> GraphError | None:
        try:
            return ResponseParser(label).parse(response, ErrorAnswer).graph_error
        except PlatformError:
            return None

    @staticmethod
    def _kind_of(code: int | None, fallback: PlatformError | None) -> tuple[FailureType, bool]:
        if code in TOKEN_REJECTED_CODES:
            return FailureType.AUTHENTICATION, False
        if code in PERMISSION_CODES:
            return FailureType.AUTHORIZATION, False
        if code in THROTTLED_CODES:
            return FailureType.RATE_LIMIT, False
        if fallback is not None:
            return fallback.type, fallback.retryable
        return FailureType.PLATFORM, False


class InstagramClient(PlatformClient):
    label = LABEL

    def __init__(self, config):
        super().__init__(config, InstagramFailureClassifier())

    @staticmethod
    def authorization(access_token: str) -> dict:
        return {"Authorization": f"OAuth {access_token}"}

    def call(
        self,
        method: str,
        path: str,
        access_token: str,
        model: type[M],
        *,
        refusal: str | None = None,
        attempts: int | None = None,
        **kwargs,
    ) -> M:
        headers = {**self.authorization(access_token), **kwargs.pop("headers", {})}
        response = self.send(method, f"{GRAPH_ROOT}/{path}", attempts=attempts, headers=headers, **kwargs)
        return self.parse(response, model, refusal=refusal)


def client() -> InstagramClient:
    return InstagramClient(container().config.http)


def send(method: str, url: str, *, attempts: int | None = None, **kwargs):
    return client().send(method, url, attempts=attempts, **kwargs)


def authorization(access_token: str) -> dict:
    return InstagramClient.authorization(access_token)


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
    return client().call(method, path, access_token, model, refusal=refusal, attempts=attempts, **kwargs)
