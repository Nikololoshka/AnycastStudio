from collections import deque
from dataclasses import dataclass, field


class FakeAnswer:
    def __init__(self, status: int = 200, body=None):
        self.status = status
        self._body = {} if body is None else body

    async def json(self, content_type=None):
        if isinstance(self._body, str):
            raise ValueError("not JSON")
        return self._body


@dataclass(frozen=True)
class SentRequest:
    method: str
    url: str
    kwargs: dict = field(default_factory=dict)

    @property
    def headers(self) -> dict:
        return self.kwargs.get("headers") or {}

    @property
    def params(self) -> dict:
        return self.kwargs.get("params") or {}

    @property
    def data(self):
        return self.kwargs.get("data")

    @property
    def json(self):
        return self.kwargs.get("json")


class FakeExchange:
    def __init__(self, outcome):
        self._outcome = outcome

    async def __aenter__(self):
        if isinstance(self._outcome, BaseException):
            raise self._outcome
        return self._outcome

    async def __aexit__(self, *exc_info) -> bool:
        return False


class FakeSession:
    def __init__(self):
        self.sent: list[SentRequest] = []
        self._answers: deque = deque()

    def answer(self, *answers) -> None:
        self._answers.extend(answers)

    def request(self, method: str, url: str, **kwargs) -> FakeExchange:
        self.sent.append(SentRequest(method, url, kwargs))
        if not self._answers:
            raise AssertionError(f"Nothing was prepared to answer {method} {url}")
        return FakeExchange(self._answers.popleft())

    @property
    def last(self) -> SentRequest:
        return self.sent[-1]

    @property
    def unanswered(self) -> int:
        return len(self._answers)
