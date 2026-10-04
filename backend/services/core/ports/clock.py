from abc import ABC, abstractmethod
from datetime import datetime


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime: ...

    @abstractmethod
    async def sleep(self, seconds: float) -> None: ...
