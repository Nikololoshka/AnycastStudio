from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime

from ..publishing.job import PublishJob
from ..publishing.status import TargetStatus


class TargetRepository(ABC):
    @abstractmethod
    def job_of(self, target_id: int) -> PublishJob: ...

    @abstractmethod
    def claim(self, target_id: int, now: datetime, abandoned_before: datetime) -> bool: ...

    @abstractmethod
    def start_attempt(self, target_id: int, now: datetime) -> None: ...

    @abstractmethod
    def update(self, target_id: int, **fields) -> None: ...

    @abstractmethod
    def cancel_requested(self, target_id: int) -> bool: ...

    @abstractmethod
    def claim_confirmation(self, target_id: int, now: datetime) -> bool: ...

    @abstractmethod
    def take_due(self, platforms: Iterable[str], now: datetime, dispatched_before: datetime) -> list[int]: ...

    @abstractmethod
    def take_stalled_confirmations(self, now: datetime, stalled_before: datetime) -> list[int]: ...

    @abstractmethod
    def ensure_owned(self, owner_id: int, target_id: int) -> None: ...

    @abstractmethod
    def status_of(self, target_id: int) -> TargetStatus: ...

    @abstractmethod
    def request_cancel(self, target_id: int, now: datetime) -> None: ...

    @abstractmethod
    def reset_for_retry(self, target_id: int) -> None: ...
