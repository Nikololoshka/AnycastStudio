import logging
from contextlib import aclosing
from dataclasses import replace
from functools import partial

from platforms.core import (
    PlatformError,
    PlatformFailure,
    PlatformRegistry,
    PublishInteractor,
    PublishJob,
    PublishOutcome,
)

from ...core.ports import AccessTokens, TargetRepository, TaskQueue
from ...core.publications.target_status import TargetStatus
from .confirmation_poller import ConfirmationPoller
from .failure_report import FailureReport
from .target_writer import TargetWriter

logger = logging.getLogger(__name__)


class _Cancelled(Exception):
    pass


class PublicationPipeline:
    def __init__(
        self,
        targets: TargetRepository,
        platforms: PlatformRegistry,
        tokens: AccessTokens,
        queue: TaskQueue,
        writer: TargetWriter,
    ):
        self._targets = targets
        self._platforms = platforms
        self._tokens = tokens
        self._queue = queue
        self._writer = writer

    async def run(self, target_id: int) -> TargetStatus | None:
        now = self._writer.now()
        if not await self._targets.claim_queued_target(target_id, now):
            logger.info("Target %s was already taken", target_id)
            return None
        await self._targets.start_target_attempt(target_id, now)

        try:
            job = await self._targets.get_publish_job(target_id)
            await self._check_cancelled(target_id)
            self._validate(job)
            media_id = await self._upload(job)
            outcome = await self._publish(replace(job, media_id=media_id))
            status = await self._writer.record(target_id, outcome)
        except _Cancelled:
            await self._writer.cancel(target_id)
            return TargetStatus.CANCELLED
        except Exception as exception:
            logger.exception("Target %s raised", target_id)
            await self._writer.fail(target_id, FailureReport.of(exception))
            return TargetStatus.FAILED

        if status == TargetStatus.PROCESSING:
            await self._queue.confirm_later(target_id, ConfirmationPoller.POLL_DELAYS_SECONDS[0])
        return status

    async def _check_cancelled(self, target_id: int) -> None:
        if await self._targets.is_cancel_requested(target_id):
            raise _Cancelled()

    def _validate(self, job: PublishJob) -> None:
        result = self._platforms.get(job.platform).validator.validate(job.draft, job.media)
        if not result.valid:
            raise PlatformError(PlatformFailure.INVALID, "; ".join(result.errors), details=",".join(result.errors))
        if not job.media.path.exists():
            raise PlatformError(PlatformFailure.MEDIA_MISSING, FailureReport.MEDIA_MISSING)

    async def _upload(self, job: PublishJob) -> str:
        size = job.media.size_bytes
        await self._writer.set(
            job.target_id,
            status=TargetStatus.UPLOADING,
            total_bytes=size,
            progress=0,
            uploaded_bytes=0,
            uploaded_media_id="",
            confirmation_state=None,
        )
        publishing = self._platforms.get(job.platform).get_publish_interactor()
        media_id = await self._tokens.run(job.account_id, partial(self._send, publishing, job))
        if media_id is None:
            raise _Cancelled()
        await self._writer.set(job.target_id, uploaded_media_id=media_id, progress=100, uploaded_bytes=size)
        return media_id

    async def _send(self, publishing: PublishInteractor, job: PublishJob, access_token: str) -> str | None:
        last_percent = 0
        async with aclosing(publishing.upload(job, access_token)) as progress_events:
            async for progress in progress_events:
                if progress.done:
                    return progress.media_id
                if progress.percent != last_percent:
                    last_percent = progress.percent
                    await self._writer.set(
                        job.target_id, progress=progress.percent, uploaded_bytes=progress.uploaded_bytes
                    )
                if await self._targets.is_cancel_requested(job.target_id):
                    return None
        raise PlatformError(PlatformFailure.UNEXPECTED, "The upload ended without a media id")

    async def _publish(self, job: PublishJob) -> PublishOutcome:
        await self._check_cancelled(job.target_id)
        await self._writer.set(job.target_id, status=TargetStatus.PUBLISHING)
        publishing = self._platforms.get(job.platform).get_publish_interactor()
        return await self._tokens.run(job.account_id, partial(publishing.publish, job))
