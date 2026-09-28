import logging
import time

from platforms import x
from platforms.core.capabilities import ValidationResult
from platforms.core.errors import FailureType, MaybePublished, NeedsFreshToken, PlatformError
from platforms.core.publishing import Confirmation, NotReady, PublicationDraft, PublishJob, Published, TargetStatus

from ..repositories import DjangoTargetRepository
from .publisher import AppPublisher

logger = logging.getLogger(__name__)

POSTING_STARTED = "posting_started"
UNANSWERED = (FailureType.NETWORK, FailureType.PLATFORM)


def _posting_started(job: PublishJob) -> float | None:
    return (job.resume_state or {}).get(POSTING_STARTED)


class XPublisher(AppPublisher):
    platform = x

    def __init__(self):
        self._targets = DjangoTargetRepository()

    def validate(self, draft: PublicationDraft) -> ValidationResult:
        media = draft.media
        return x.validate(
            caption=draft.caption(),
            size_bytes=media.size_bytes,
            mime_type=media.mime_type,
            duration_seconds=media.duration_seconds,
        )

    def upload(self, job: PublishJob, access_token: str, on_progress, should_cancel) -> str:
        media = job.draft.media
        return x.upload(
            path=job.video_path,
            size=media.size_bytes,
            mime_type=media.mime_type,
            access_token=access_token,
            resume=x.ResumeState.of(job.resume_state),
            on_progress=on_progress,
            should_cancel=should_cancel,
        )

    def publish(self, job: PublishJob, media_id: str, access_token: str) -> Published:
        started = _posting_started(job)
        if started is None:
            return Published.awaiting_confirmation()
        return Published.awaiting_confirmation(**{POSTING_STARTED: started})

    def _post(self, job: PublishJob, access_token: str) -> str:
        before = dict(job.resume_state or {})
        self._targets.update(job.target_id, resume_state={**before, POSTING_STARTED: time.time()})
        options = x.video_options_of(job.draft.settings)
        try:
            return x.create_post(access_token, job.draft.caption(), job.uploaded_media_id, options)
        except NeedsFreshToken:
            self._targets.update(job.target_id, resume_state=before)
            raise
        except PlatformError as failure:
            if failure.type not in UNANSWERED:
                self._targets.update(job.target_id, resume_state=before)
                raise
            raise MaybePublished(self.label, failure.details) from None

    def confirm(self, job: PublishJob, access_token: str) -> Confirmation:
        if _posting_started(job) is not None:
            raise MaybePublished(self.label)

        status = x.fetch_status(access_token, job.uploaded_media_id)
        if status.is_failed:
            raise x.failure_of(status)
        if not status.is_ready:
            return NotReady()

        post_id = self._post(job, access_token)
        logger.info("Target %s: X post %s created", job.target_id, post_id)
        return Published(TargetStatus.COMPLETED, x.post_url(post_id))
