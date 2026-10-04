from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime

from platforms.core import PlatformType, PublishJob

from ..publications.target_status import TargetStatus


class TargetRepository(ABC):
    @abstractmethod
    async def job_of(self, target_id: int) -> PublishJob: ...

    @abstractmethod
    async def claim(self, target_id: int, now: datetime) -> bool: ...

    @abstractmethod
    async def start_attempt(self, target_id: int, now: datetime) -> None: ...

    @abstractmethod
    async def update(self, target_id: int, **fields) -> None: ...

    @abstractmethod
    async def cancel_requested(self, target_id: int) -> bool: ...

    @abstractmethod
    async def claim_confirmation(self, target_id: int, now: datetime) -> bool: ...

    @abstractmethod
    async def take_due(
        self, platforms: Iterable[PlatformType], now: datetime, dispatched_before: datetime
    ) -> list[int]: ...

    @abstractmethod
    async def take_stalled_confirmations(self, now: datetime, stalled_before: datetime) -> list[int]: ...

    @abstractmethod
    async def fail_abandoned(self, now: datetime, abandoned_before: datetime, failure: dict) -> list[int]: ...

    @abstractmethod
    async def ensure_owned(self, owner_id: int, target_id: int) -> None: ...

    @abstractmethod
    async def status_of(self, target_id: int) -> TargetStatus: ...

    @abstractmethod
    async def request_cancel(self, target_id: int, now: datetime) -> None: ...

    @abstractmethod
    async def reset_for_retry(self, target_id: int) -> None: ...
