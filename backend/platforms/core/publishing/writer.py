import logging
from datetime import datetime

from ..ports import Clock, TargetRepository
from .outcome import Published
from .status import TargetStatus

logger = logging.getLogger(__name__)

CONFIRMING_SINCE = "confirming_since"
POLLS = "polls"


class TargetWriter:
    def __init__(self, targets: TargetRepository, clock: Clock):
        self._targets = targets
        self._clock = clock

    def now(self) -> datetime:
        return self._clock.now()

    def set(self, target_id: int, **fields) -> None:
        self._targets.update(target_id, last_activity_at=self.now(), **fields)

    def fail(self, target_id: int, failure: dict) -> None:
        self.set(target_id, status=TargetStatus.FAILED, error=failure, finished_at=self.now())
        logger.info("Target %s failed: %s", target_id, failure.get("message"))

    def cancel(self, target_id: int) -> None:
        self.set(target_id, status=TargetStatus.CANCELLED, finished_at=self.now())

    def record(self, target_id: int, published: Published, kept: dict | None = None) -> None:
        state = published.resume_state
        if published.status == TargetStatus.PROCESSING:
            state = {**(kept or {}), **(state or {}), CONFIRMING_SINCE: self.now().isoformat(), POLLS: 0}
        fields = {"status": published.status, "published_url": published.url, "resume_state": state}
        if not TargetStatus(published.status).is_active:
            fields["finished_at"] = self.now()
        self.set(target_id, **fields)
        logger.info("Target %s is now %s", target_id, published.status)
