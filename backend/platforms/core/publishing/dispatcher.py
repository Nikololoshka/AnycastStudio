import logging
from datetime import timedelta

from ..platform import PlatformCatalog
from ..ports import TargetRepository, TaskQueue
from .writer import TargetWriter

logger = logging.getLogger(__name__)


class DeferredDispatcher:
    REDISPATCH_AFTER = timedelta(minutes=15)
    CONFIRMATION_STALLED_AFTER = timedelta(minutes=5)

    def __init__(self, targets: TargetRepository, catalog: PlatformCatalog, queue: TaskQueue, writer: TargetWriter):
        self._targets = targets
        self._catalog = catalog
        self._queue = queue
        self._writer = writer

    def dispatch(self) -> int:
        now = self._writer.now()

        due = self._targets.take_due(self._catalog.deferring_upload(), now, now - self.REDISPATCH_AFTER)
        for target_id in due:
            self._queue.run_target(target_id)
        if due:
            logger.info("Dispatched %d targets whose time has come", len(due))

        stalled = self._targets.take_stalled_confirmations(now, now - self.CONFIRMATION_STALLED_AFTER)
        for target_id in stalled:
            self._queue.confirm_now(target_id)
        if stalled:
            logger.info("Resumed confirming %d targets", len(stalled))

        return len(due)
