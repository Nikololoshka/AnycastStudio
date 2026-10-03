from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..auth import AuthFailure


@dataclass(frozen=True)
class PlatformResponse(ABC):
    status: int
    body: dict

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @abstractmethod
    def failure(self) -> AuthFailure: ...

    @abstractmethod
    def refusal(self) -> str: ...
