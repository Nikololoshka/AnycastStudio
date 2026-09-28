import logging
from datetime import UTC, datetime, timedelta

from ..errors import FailureType
from ..platform import PlatformCatalog
from ..ports import AccessTokens, TargetRepository, TaskQueue
from .commit import CommitGuard
from .failures import FailureMapper
from .job import PublishJob
from .outcome import NotReady, Published, ReadyToCommit
from .writer import CONFIRMING_SINCE, POLLS, TargetWriter

logger = logging.getLogger(__name__)


class ConfirmationPoller:
    POLL_DELAYS_SECONDS = (10, 30, 60, 120)
    CONFIRM_WITHIN_SECONDS = 30 * 60

    def __init__(
        self,
        targets: TargetRepository,
        catalog: PlatformCatalog,
        tokens: AccessTokens,
        queue: TaskQueue,
        writer: TargetWriter,
        failures: FailureMapper,
        commits: CommitGuard,
    ):
        self._targets = targets
        self._catalog = catalog
        self._tokens = tokens
        self._queue = queue
        self._writer = writer
        self._failures = failures
        self._commits = commits

    def confirm(self, target_id: int) -> int | None:
        now = self._writer.now()
        if not self._targets.claim_confirmation(target_id, now):
            logger.info("Target %s is not waiting for confirmation", target_id)
            return None

        job = self._targets.job_of(target_id)
        state = job.resume_state or {}
        polls = int(state.get(POLLS, 0))
        since = self._since(state, now)

        try:
            published = self._ask(job)
        except Exception as exception:
            logger.exception("Target %s raised while confirming", target_id)
            self._writer.fail(target_id, self._failures.failure_of(exception))
            return None

        if published is not None:
            self._writer.record(target_id, published)
            return None

        if now - since >= timedelta(seconds=self.CONFIRM_WITHIN_SECONDS):
            message = "The platform did not confirm the publish in time; check it there"
            self._writer.fail(target_id, {"type": FailureType.PLATFORM.value, "message": message})
            return None

        self._writer.set(target_id, resume_state={**state, CONFIRMING_SINCE: since.isoformat(), POLLS: polls + 1})
        delay = self.POLL_DELAYS_SECONDS[min(polls + 1, len(self.POLL_DELAYS_SECONDS) - 1)]
        self._queue.confirm_later(target_id, delay)
        return delay

    def _ask(self, job: PublishJob) -> Published | None:
        publisher = self._catalog.get(job.platform).publisher
        if self._commits.was_started(job):
            return self._commits.resolve(job, publisher)

        confirmation = self._tokens.run(job.account_id, lambda token: publisher.confirm(job, token))
        if isinstance(confirmation, NotReady):
            return None
        if isinstance(confirmation, ReadyToCommit):
            return self._commits.commit(job, publisher)
        return confirmation

    @staticmethod
    def _since(state: dict, now: datetime) -> datetime:
        raw = state.get(CONFIRMING_SINCE)
        if isinstance(raw, (int, float)):
            return datetime.fromtimestamp(raw, UTC)
        if isinstance(raw, str):
            try:
                return datetime.fromisoformat(raw)
            except ValueError:
                return now
        return now
