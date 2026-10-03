import logging
from datetime import timedelta

from ...platform_registry import PlatformRegistry
from ...ports import TargetRepository, TaskQueue
from .target_writer import TargetWriter

logger = logging.getLogger(__name__)


class DeferredDispatcher:
    REDISPATCH_AFTER = timedelta(minutes=15)
    CONFIRMATION_STALLED_AFTER = timedelta(minutes=5)

    def __init__(
        self, targets: TargetRepository, platforms: PlatformRegistry, queue: TaskQueue, writer: TargetWriter
    ):
        self._targets = targets
        self._platforms = platforms
        self._queue = queue
        self._writer = writer

    async def dispatch(self) -> int:
        now = self._writer.now()

        due = await self._targets.take_due(self._platforms.deferring_upload(), now, now - self.REDISPATCH_AFTER)
        for target_id in due:
            await self._queue.run_target(target_id)
        if due:
            logger.info("Dispatched %d targets whose time has come", len(due))

        stalled = await self._targets.take_stalled_confirmations(now, now - self.CONFIRMATION_STALLED_AFTER)
        for target_id in stalled:
            await self._queue.confirm_now(target_id)
        if stalled:
            logger.info("Resumed confirming %d targets", len(stalled))

        return len(due)
