from typing import TypeVar

from pydantic import BaseModel

from config.wiring import container

from ..core.errors import FailureType, PlatformError
from ..core.http import FailureClassifier, PlatformClient, ResponseParser
from .responses import Data, Problem, ProblemAnswer

LABEL = "X"
API_ROOT = "https://api.x.com/2"

USAGE_CAPPED = "usage-capped"
CLIENT_FORBIDDEN = "client-forbidden"

M = TypeVar("M", bound=BaseModel)


class XFailureClassifier(FailureClassifier):
    def classify(self, response, label: str) -> PlatformError | None:
        failure = super().classify(response, label)
        if failure is None:
            return None

        problem = self._problem_of(response, label)
        kind = problem.kind
        message = (problem.text or failure.message)[:500]

        if kind == USAGE_CAPPED:
            return PlatformError(FailureType.RATE_LIMIT, message, details=kind)
        if kind == CLIENT_FORBIDDEN:
            return PlatformError(FailureType.AUTHORIZATION, message, details=kind)
        return PlatformError(failure.type, message, details=kind, retryable=failure.retryable)

    @staticmethod
    def _problem_of(response, label: str) -> Problem:
        try:
            return ResponseParser(label).parse(response, ProblemAnswer).problem
        except PlatformError:
            return Problem()


class XClient(PlatformClient):
    label = LABEL

    def __init__(self, config):
        super().__init__(config, XFailureClassifier())

    @staticmethod
    def bearer(access_token: str) -> dict:
        return {"Authorization": f"Bearer {access_token}"}

    def call(self, method: str, path: str, access_token: str, *, attempts: int | None = None, **kwargs):
        headers = {**self.bearer(access_token), **kwargs.pop("headers", {})}
        return self.send(method, f"{API_ROOT}/{path}", attempts=attempts, headers=headers, **kwargs)

    def data_of(self, response, model: type[M], *, refusal: str | None = None) -> M:
        return self.parse(response, Data[model], refusal=refusal).data


def client() -> XClient:
    return XClient(container().config.http)


def send(method: str, url: str, *, attempts: int | None = None, **kwargs):
    return client().send(method, url, attempts=attempts, **kwargs)


def bearer(access_token: str) -> dict:
    return XClient.bearer(access_token)


def call(method: str, path: str, access_token: str, *, attempts: int | None = None, **kwargs):
    return client().call(method, path, access_token, attempts=attempts, **kwargs)


def data_of(response, model: type[M], *, refusal: str | None = None) -> M:
    return client().data_of(response, model, refusal=refusal)
