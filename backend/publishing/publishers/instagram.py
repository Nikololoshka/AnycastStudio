import logging
import time

from media import storage
from platforms import instagram
from platforms.capabilities import ValidationResult
from platforms.http import PlatformFailure

from ..models import PublicationTarget
from .outcome import Published

logger = logging.getLogger(__name__)

Status = PublicationTarget.Status

capabilities = instagram.capabilities


def _options(target: PublicationTarget) -> instagram.VideoOptions:
    return instagram.video_options_of(target.settings)


def _caption(target: PublicationTarget) -> str:
    publication = target.publication
    return instagram.caption_of(publication.title, publication.description, list(publication.hashtags))


def validate(target: PublicationTarget) -> ValidationResult:
    asset = target.publication.asset
    return instagram.validate(
        caption=_caption(target),
        size_bytes=asset.size_bytes,
        mime_type=asset.mime_type,
        duration_seconds=asset.duration_seconds,
    )


def _reel_info(target: PublicationTarget) -> instagram.ReelInfo:
    options = _options(target)
    return instagram.ReelInfo(
        caption=_caption(target),
        share_to_feed=options.share_to_feed,
        thumb_offset_ms=options.thumb_offset_ms,
    )


def upload(target: PublicationTarget, access_token: str, resume: dict | None, on_progress, should_cancel) -> str:
    asset = target.publication.asset
    return instagram.upload(
        path=storage.absolute(asset.storage_path),
        size=asset.size_bytes,
        ig_user_id=target.social_account.external_id,
        reel=_reel_info(target),
        access_token=access_token,
        resume=instagram.ResumeState.of(resume),
        on_progress=lambda uploaded, total, state: on_progress(uploaded, total, state.as_dict()),
        should_cancel=should_cancel,
    )


def publish(target: PublicationTarget, container_id: str, access_token: str) -> Published:
    return Published(Status.PROCESSING, resume_state={"confirming_since": time.time(), "polls": 0})


def _url_of(media_id: str, access_token: str) -> str:
    try:
        return instagram.permalink(access_token, media_id)
    except PlatformFailure as failure:
        logger.info("Could not learn the Instagram post link: %s", failure.type)
        return ""


def _published_media_id(target: PublicationTarget, access_token: str) -> str | None:
    try:
        return instagram.publish_container(access_token, target.social_account.external_id, target.uploaded_media_id)
    except PlatformFailure as failure:
        if failure.retryable:
            logger.info("Target %s: Instagram publish did not answer, asking again later", target.pk)
            return None
        raise


def confirm(target: PublicationTarget, access_token: str) -> Published | None:
    status = instagram.container_status(access_token, target.uploaded_media_id)
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
