import logging
from datetime import timedelta

from platforms.core import PlatformError, PlatformFailure

from ...core.ports import Clock, TargetRepository

logger = logging.getLogger(__name__)


class StaleTargetSweeper:
    ABANDONED_AFTER = timedelta(minutes=15)
    WORKER_STOPPED = "The worker stopped before the publish finished; publish again"

    def __init__(self, targets: TargetRepository, clock: Clock):
        self._targets = targets
        self._clock = clock

    async def sweep(self) -> int:
        now = self._clock.now()
        failure = PlatformError(PlatformFailure.UNEXPECTED, self.WORKER_STOPPED).as_failure()
        failed = await self._targets.fail_abandoned(now, now - self.ABANDONED_AFTER, failure)
        if failed:
            logger.info("Failed %d targets abandoned by a stopped worker: %s", len(failed), failed)
        return len(failed)
