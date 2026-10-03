from abc import ABC, abstractmethod


class TaskQueue(ABC):
    @abstractmethod
    async def run_target(self, target_id: int) -> None: ...

    @abstractmethod
    async def confirm_now(self, target_id: int) -> None: ...

    @abstractmethod
    async def confirm_later(self, target_id: int, delay_seconds: int) -> None: ...
