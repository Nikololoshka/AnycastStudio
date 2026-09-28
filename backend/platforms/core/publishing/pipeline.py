import logging
from datetime import timedelta

from ..errors import FailureType, MediaMissing, NeedsFreshToken, PlatformError, UploadCancelled
from ..platform import PlatformCatalog
from ..ports import AccessTokens, TargetRepository, TaskQueue
from .commit import CommitGuard
from .confirmation import ConfirmationPoller
from .failures import FailureMapper
from .job import PublishJob
from .progress import ProgressRecorder
from .status import TargetStatus
from .writer import TargetWriter

logger = logging.getLogger(__name__)


class _Cancelled(Exception):
    pass


class PublicationPipeline:
    ABANDONED_AFTER = timedelta(minutes=15)

    def __init__(
        self,
        targets: TargetRepository,
        catalog: PlatformCatalog,
        tokens: AccessTokens,
        queue: TaskQueue,
        writer: TargetWriter,
        failures: FailureMapper,
    ):
        self._targets = targets
        self._catalog = catalog
        self._tokens = tokens
        self._queue = queue
        self._writer = writer
        self._failures = failures

    def claim(self, target_id: int) -> PublishJob | None:
        now = self._writer.now()
        if not self._targets.claim(target_id, now, now - self.ABANDONED_AFTER):
            return None
        return self._targets.job_of(target_id)

    def run(self, target_id: int) -> TargetStatus | None:
        job = self.claim(target_id)
        if job is None:
            logger.info("Target %s was already taken", target_id)
            return None

        self._targets.start_attempt(target_id, self._writer.now())

        try:
            self._check_cancelled(target_id)
            self._validate(job)
            media_id = self._upload(job)
            status = self._publish(target_id, media_id)
        except _Cancelled:
            self._writer.cancel(target_id)
            return TargetStatus.CANCELLED
        except Exception as exception:
            logger.exception("Target %s raised", target_id)
            self._writer.fail(target_id, self._failures.failure_of(exception))
            return TargetStatus.FAILED

        if status == TargetStatus.PROCESSING:
            self._queue.confirm_later(target_id, ConfirmationPoller.POLL_DELAYS_SECONDS[0])
        return status

    def _check_cancelled(self, target_id: int) -> None:
        if self._targets.cancel_requested(target_id):
            raise _Cancelled()

    def _validate(self, job: PublishJob) -> None:
        result = self._catalog.get(job.platform).validator.validate(job.draft)
        if not result.valid:
            raise PlatformError(FailureType.VALIDATION, "; ".join(result.errors), details=",".join(result.errors))
        if not job.video_path.exists():
            raise MediaMissing()

    def _upload(self, job: PublishJob) -> str:
        if job.uploaded_media_id:
            return job.uploaded_media_id

        target_id = job.target_id
        size = job.draft.media.size_bytes
        publisher = self._catalog.get(job.platform).publisher
        progress = ProgressRecorder(self._writer, target_id)
        self._writer.set(target_id, status=TargetStatus.UPLOADING, total_bytes=size)

        def send(access_token: str) -> str:
            return publisher.upload(
                self._targets.job_of(target_id),
                access_token,
                on_progress=progress,
                should_cancel=lambda: self._targets.cancel_requested(target_id),
            )

        def keep_resume_point(rejection: NeedsFreshToken) -> None:
            logger.info("Target %s: refreshing the token and resuming", target_id)
            if rejection.state is not None:
                self._writer.set(target_id, resume_state=rejection.state)

        try:
            media_id = self._tokens.run(job.account_id, send, on_rejected=keep_resume_point)
        except UploadCancelled as cancelled:
            self._writer.set(target_id, resume_state=cancelled.state)
            raise _Cancelled() from None

        self._writer.set(target_id, uploaded_media_id=media_id, progress=100, uploaded_bytes=size)
        return media_id

    def _publish(self, target_id: int, media_id: str) -> TargetStatus:
        self._check_cancelled(target_id)
        self._writer.set(target_id, status=TargetStatus.PUBLISHING)

        job = self._targets.job_of(target_id)
        publisher = self._catalog.get(job.platform).publisher
        published = publisher.publish(job, media_id, self._tokens.valid(job.account_id))
        self._writer.record(target_id, published, kept=CommitGuard.marker_of(job))
        return TargetStatus(published.status)
