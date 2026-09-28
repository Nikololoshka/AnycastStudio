import logging

from platforms import instagram
from platforms.core.capabilities import ValidationResult
from platforms.core.errors import PlatformError

from ..models import PublicationTarget
from .outcome import Published
from .publisher import Publisher

logger = logging.getLogger(__name__)

Status = PublicationTarget.Status


def _url_of(media_id: str, access_token: str) -> str:
    try:
        return instagram.post_url(access_token, media_id)
    except PlatformError as failure:
        logger.info("Could not learn the Instagram post link: %s", failure.type)
        return ""


def _published_media_id(target: PublicationTarget, access_token: str) -> str | None:
    try:
        return instagram.publish_container(access_token, target.social_account.external_id, target.uploaded_media_id)
    except PlatformError as failure:
        if failure.retryable:
            logger.info("Target %s: Instagram publish did not answer, asking again later", target.pk)
            return None
        raise


class InstagramPublisher(Publisher):
    platform = instagram

    def validate(self, target: PublicationTarget) -> ValidationResult:
        asset = target.publication.asset
        return instagram.validate(
            caption=self.caption(target),
            size_bytes=asset.size_bytes,
            mime_type=asset.mime_type,
            duration_seconds=asset.duration_seconds,
        )

    def _reel_info(self, target: PublicationTarget) -> instagram.ReelInfo:
        options = instagram.video_options_of(target.settings)
        return instagram.ReelInfo(
            caption=self.caption(target),
            share_to_feed=options.share_to_feed,
            thumb_offset_ms=options.thumb_offset_ms,
        )

    def upload(
        self, target: PublicationTarget, access_token: str, resume: dict | None, on_progress, should_cancel
    ) -> str:
        return instagram.upload(
            path=self.file_of(target),
            size=target.publication.asset.size_bytes,
            ig_user_id=target.social_account.external_id,
            reel=self._reel_info(target),
            access_token=access_token,
            resume=instagram.ResumeState.of(resume),
            on_progress=on_progress,
            should_cancel=should_cancel,
        )

    def confirm(self, target: PublicationTarget, access_token: str) -> Published | None:
        status = instagram.fetch_status(access_token, target.uploaded_media_id)
        if status.is_published:
            return Published(Status.COMPLETED)
        if status.is_dead:
            raise instagram.failure_of(status)
        if not status.is_ready:
            return None

        media_id = _published_media_id(target, access_token)
        if media_id is None:
            return None
        return Published(Status.COMPLETED, _url_of(media_id, access_token))
