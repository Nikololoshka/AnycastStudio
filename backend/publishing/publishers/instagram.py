import logging

from platforms import instagram
from platforms.core.capabilities import ValidationResult
from platforms.core.errors import PlatformError
from platforms.core.publishing import Confirmation, NotReady, Published, PublishJob, TargetStatus

from .publisher import AppPublisher

logger = logging.getLogger(__name__)


def _url_of(media_id: str, access_token: str) -> str:
    try:
        return instagram.post_url(access_token, media_id)
    except PlatformError as failure:
        logger.info("Could not learn the Instagram post link: %s", failure.type)
        return ""


def _published_media_id(job: PublishJob, access_token: str) -> str | None:
    try:
        return instagram.publish_container(access_token, job.external_id, job.uploaded_media_id)
    except PlatformError as failure:
        if failure.retryable:
            logger.info("Target %s: Instagram publish did not answer, asking again later", job.target_id)
            return None
        raise


class InstagramPublisher(AppPublisher):
    platform = instagram

    def validate(self, job: PublishJob) -> ValidationResult:
        media = job.draft.media
        return instagram.validate(
            caption=job.draft.caption(),
            size_bytes=media.size_bytes,
            mime_type=media.mime_type,
            duration_seconds=media.duration_seconds,
        )

    def _reel_info(self, job: PublishJob) -> instagram.ReelInfo:
        options = instagram.video_options_of(job.draft.settings)
        return instagram.ReelInfo(
            caption=job.draft.caption(),
            share_to_feed=options.share_to_feed,
            thumb_offset_ms=options.thumb_offset_ms,
        )

    def upload(self, job: PublishJob, access_token: str, on_progress, should_cancel) -> str:
        return instagram.upload(
            path=job.video_path,
            size=job.draft.media.size_bytes,
            ig_user_id=job.external_id,
            reel=self._reel_info(job),
            access_token=access_token,
            resume=instagram.ResumeState.of(job.resume_state),
            on_progress=on_progress,
            should_cancel=should_cancel,
        )

    def confirm(self, job: PublishJob, access_token: str) -> Confirmation:
        status = instagram.fetch_status(access_token, job.uploaded_media_id)
        if status.is_published:
            return Published(TargetStatus.COMPLETED)
        if status.is_dead:
            raise instagram.failure_of(status)
        if not status.is_ready:
            return NotReady()

        media_id = _published_media_id(job, access_token)
        if media_id is None:
            return NotReady()
        return Published(TargetStatus.COMPLETED, _url_of(media_id, access_token))
