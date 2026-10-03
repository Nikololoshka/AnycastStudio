from abc import ABC, abstractmethod


class Cache(ABC):
    @abstractmethod
    async def get(self, key: str): ...

    @abstractmethod
    async def set(self, key: str, value, seconds: int) -> None: ...
