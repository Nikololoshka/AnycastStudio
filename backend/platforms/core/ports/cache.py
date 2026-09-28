from abc import ABC, abstractmethod


class Cache(ABC):
    @abstractmethod
    def get(self, key: str): ...

    @abstractmethod
    def set(self, key: str, value, seconds: int) -> None: ...
