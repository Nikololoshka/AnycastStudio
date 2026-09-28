from typing import TypeVar

from pydantic import BaseModel

from ..config import HttpConfig
from .failures import FailureClassifier
from .parsing import ResponseParser
from .retry import RetryPolicy
from .transport import Transport

M = TypeVar("M", bound=BaseModel)


class PlatformClient:
    label: str = ""

    def __init__(self, config: HttpConfig, classifier: FailureClassifier | None = None, label: str | None = None):
        self.label = label or self.label
        self.parser = ResponseParser(self.label)
        self._transport = Transport(config.timeout)
        self._retry = RetryPolicy(config.attempts)
        self._classifier = classifier or FailureClassifier()

    def send(self, method: str, url: str, *, attempts: int | None = None, **kwargs):
        def attempt():
            response = self._transport.request(method, url, label=self.label, **kwargs)
            failure = self._classifier.classify(response, self.label)
            if failure is not None:
                raise failure
            return response

        return self._retry.run(attempt, label=self.label, attempts=attempts)

    def parse(self, response, model: type[M], *, refusal: str | None = None) -> M:
        return self.parser.parse(response, model, refusal=refusal)

    def parse_body(self, body, model: type[M], *, refusal: str | None = None) -> M:
        return self.parser.parse_body(body, model, refusal=refusal)
