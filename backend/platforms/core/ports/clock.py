import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime: ...

    @abstractmethod
    def sleep(self, seconds: float) -> None: ...


class SystemClock(Clock):
    def now(self) -> datetime:
        return datetime.now(UTC)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)
