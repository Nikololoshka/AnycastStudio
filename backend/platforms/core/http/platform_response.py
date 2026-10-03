from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..platform_failure import PlatformFailure


@dataclass(frozen=True)
class PlatformResponse(ABC):
    status: int
    body: dict

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @abstractmethod
    def failure(self) -> PlatformFailure: ...

    @abstractmethod
    def refusal(self) -> str: ...
