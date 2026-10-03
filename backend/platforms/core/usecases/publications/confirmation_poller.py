import logging
from datetime import UTC, datetime, timedelta
from functools import partial

from ...platform_error import PlatformError
from ...platform_failure import PlatformFailure
from ...platform_registry import PlatformRegistry
from ...ports import AccessTokens, TargetRepository, TaskQueue
from ...publish import NotReady, PublishJob, Published, ReadyToCommit
from .commit_guard import CommitGuard
from .failure_report import FailureReport
from .target_writer import TargetWriter

logger = logging.getLogger(__name__)


class ConfirmationPoller:
    POLL_DELAYS_SECONDS = (10, 30, 60, 120)
    CONFIRM_WITHIN = timedelta(minutes=30)
    NOT_CONFIRMED = "The platform did not confirm the publish in time; check it there"

    def __init__(
        self,
        targets: TargetRepository,
        platforms: PlatformRegistry,
        tokens: AccessTokens,
        queue: TaskQueue,
        writer: TargetWriter,
        commits: CommitGuard,
    ):
        self._targets = targets
        self._platforms = platforms
        self._tokens = tokens
        self._queue = queue
        self._writer = writer
        self._commits = commits

    async def confirm(self, target_id: int) -> int | None:
        now = self._writer.now()
        if not await self._targets.claim_confirmation(target_id, now):
            logger.info("Target %s is not waiting for confirmation", target_id)
            return None

        job = await self._targets.job_of(target_id)
        state = dict(job.confirmation_state)
        polls = int(state.get(TargetWriter.POLLS, 0))
        since = self._since(state, now)

        try:
            published = await self._ask(job)
        except Exception as exception:
            logger.exception("Target %s raised while confirming", target_id)
            await self._writer.fail(target_id, FailureReport.of(exception))
            return None

        if published is not None:
            await self._writer.finish(target_id, published)
            return None

        if now - since >= self.CONFIRM_WITHIN:
            failure = PlatformError(PlatformFailure.UNCONFIRMED, self.NOT_CONFIRMED)
            await self._writer.fail(target_id, failure.as_failure())
            return None

        confirming = {**state, TargetWriter.CONFIRMING_SINCE: since.isoformat(), TargetWriter.POLLS: polls + 1}
        await self._writer.set(target_id, confirmation_state=confirming)
        delay = self.POLL_DELAYS_SECONDS[min(polls + 1, len(self.POLL_DELAYS_SECONDS) - 1)]
        await self._queue.confirm_later(target_id, delay)
        return delay

    async def _ask(self, job: PublishJob) -> Published | None:
        if self._commits.was_started(job):
            return await self._commits.resolve(job)

        publishing = self._platforms.get(job.platform).get_publish_interactor()
        match await self._tokens.run(job.account_id, partial(publishing.confirm, job)):
            case NotReady():
                return None
            case ReadyToCommit():
                return await self._commits.commit(job)
            case Published() as published:
                return published

    @staticmethod
    def _since(state: dict, now: datetime) -> datetime:
        raw = state.get(TargetWriter.CONFIRMING_SINCE)
        if isinstance(raw, (int, float)):
            return datetime.fromtimestamp(raw, UTC)
        if isinstance(raw, str):
            try:
                return datetime.fromisoformat(raw)
            except ValueError:
                return now
        return now
