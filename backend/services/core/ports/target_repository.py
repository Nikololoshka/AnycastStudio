from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime

from platforms.core import PlatformType, PublishJob

from ..publications.target_status import TargetStatus


class TargetRepository(ABC):
    @abstractmethod
    async def get_publish_job(self, target_id: int) -> PublishJob: ...

    @abstractmethod
    async def claim_queued_target(self, target_id: int, now: datetime) -> bool: ...

    @abstractmethod
    async def start_target_attempt(self, target_id: int, now: datetime) -> None: ...

    @abstractmethod
    async def update_target(self, target_id: int, **fields) -> None: ...

    @abstractmethod
    async def is_cancel_requested(self, target_id: int) -> bool: ...

    @abstractmethod
    async def claim_confirmation_poll(self, target_id: int, now: datetime) -> bool: ...

    @abstractmethod
    async def claim_due_targets(
        self, platforms: Iterable[PlatformType], now: datetime, dispatched_before: datetime
    ) -> list[int]: ...

    @abstractmethod
    async def claim_stalled_confirmations(self, now: datetime, stalled_before: datetime) -> list[int]: ...

    @abstractmethod
    async def fail_abandoned_targets(self, now: datetime, abandoned_before: datetime, failure: dict) -> list[int]: ...

    @abstractmethod
    async def ensure_target_owned(self, owner_id: int, target_id: int) -> None: ...

    @abstractmethod
    async def get_target_status(self, target_id: int) -> TargetStatus: ...

    @abstractmethod
    async def request_target_cancel(self, target_id: int, now: datetime) -> None: ...

    @abstractmethod
    async def reset_target_for_retry(self, target_id: int) -> None: ...
