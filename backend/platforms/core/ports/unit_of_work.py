from abc import ABC, abstractmethod
from collections.abc import Callable
from contextlib import AbstractContextManager


class UnitOfWork(ABC):
    @abstractmethod
    def atomic(self) -> AbstractContextManager: ...

    @abstractmethod
    def on_commit(self, action: Callable[[], None]) -> None: ...
