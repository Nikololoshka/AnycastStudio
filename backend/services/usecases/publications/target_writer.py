import logging
from datetime import datetime

from platforms.core import AwaitingConfirmation, PublishOutcome, Published, Scheduled

from ...core.ports import Clock, TargetRepository
from ...core.publications.target_status import TargetStatus

logger = logging.getLogger(__name__)


class TargetWriter:
    CONFIRMING_SINCE = "confirming_since"
    POLLS = "polls"

    def __init__(self, targets: TargetRepository, clock: Clock):
        self._targets = targets
        self._clock = clock

    def now(self) -> datetime:
        return self._clock.now()

    async def set(self, target_id: int, **fields) -> None:
        await self._targets.update(target_id, last_activity_at=self.now(), **fields)

    async def fail(self, target_id: int, failure: dict) -> None:
        await self.set(target_id, status=TargetStatus.FAILED, error=failure, finished_at=self.now())
        logger.info("Target %s failed: %s (%s)", target_id, failure.get("message"), failure.get("failure"))

    async def cancel(self, target_id: int) -> None:
        await self.set(target_id, status=TargetStatus.CANCELLED, finished_at=self.now())

    async def finish(self, target_id: int, published: Published) -> None:
        await self.set(
            target_id, status=TargetStatus.COMPLETED, published_url=published.url, finished_at=self.now()
        )
        logger.info("Target %s is now %s", target_id, TargetStatus.COMPLETED)

    async def record(self, target_id: int, outcome: PublishOutcome) -> TargetStatus:
        match outcome:
            case Published():
                await self.finish(target_id, outcome)
                return TargetStatus.COMPLETED
            case Scheduled(url=url):
                await self.set(target_id, status=TargetStatus.SCHEDULED, published_url=url, finished_at=self.now())
                status = TargetStatus.SCHEDULED
            case AwaitingConfirmation(confirmation_state=state):
                confirming = {**state, self.CONFIRMING_SINCE: self.now().isoformat(), self.POLLS: 0}
                await self.set(target_id, status=TargetStatus.PROCESSING, confirmation_state=confirming)
                status = TargetStatus.PROCESSING
        logger.info("Target %s is now %s", target_id, status)
        return status
