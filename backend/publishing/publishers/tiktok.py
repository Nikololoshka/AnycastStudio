import logging
import time

from media import storage
from platforms import tiktok
from platforms.capabilities import ValidationResult
from platforms.http import VALIDATION, PlatformFailure
from platforms.upload import NeedsFreshToken

from ..models import PublicationTarget
from .outcome import Published

logger = logging.getLogger(__name__)

Status = PublicationTarget.Status

capabilities = tiktok.capabilities


def _options(target: PublicationTarget) -> tiktok.VideoOptions:
    return tiktok.video_options_of(target.settings)


def _caption(target: PublicationTarget) -> str:
    publication = target.publication
    return tiktok.caption_of(publication.title, publication.description, list(publication.hashtags))


def validate(target: PublicationTarget) -> ValidationResult:
    asset = target.publication.asset
    return tiktok.validate(
        caption=_caption(target),
        options=_options(target),
        size_bytes=asset.size_bytes,
        mime_type=asset.mime_type,
    )


def creator_refusals(creator: tiktok.CreatorInfo, options: tiktok.VideoOptions, duration_seconds) -> list[str]:
    refusals: list[str] = []
    if options.privacy_level not in creator.privacy_level_options:
        refusals.append("privacyNotOffered")
    limit = creator.max_video_post_duration_sec
    if limit and duration_seconds and duration_seconds > limit:
        refusals.append("videoTooLong")
    return refusals


def _post_info(target: PublicationTarget, options: tiktok.VideoOptions, creator: tiktok.CreatorInfo) -> tiktok.PostInfo:
    return tiktok.PostInfo(
        title=_caption(target),
        privacy_level=options.privacy_level or "",
        disable_comment=options.disable_comment or creator.comment_disabled,
        disable_duet=options.disable_duet or creator.duet_disabled,
        disable_stitch=options.disable_stitch or creator.stitch_disabled,
        brand_content_toggle=options.brand_content_toggle,
        brand_organic_toggle=options.brand_organic_toggle,
        is_aigc=options.is_aigc,
        video_cover_timestamp_ms=options.cover_timestamp_ms,
    )


def upload(target: PublicationTarget, access_token: str, resume: dict | None, on_progress, should_cancel) -> str:
    asset = target.publication.asset
    options = _options(target)
    creator = tiktok.creator_info(access_token)
    refusals = creator_refusals(creator, options, asset.duration_seconds)
    if refusals:
        raise PlatformFailure(VALIDATION, "; ".join(refusals), details=",".join(refusals))

    return tiktok.upload(
        path=storage.absolute(asset.storage_path),
        size=asset.size_bytes,
        mime_type=asset.mime_type,
        post_info=_post_info(target, options, creator),
        access_token=access_token,
        resume=tiktok.ResumeState.of(resume),
        on_progress=on_progress,
        should_cancel=should_cancel,
    )


def publish(target: PublicationTarget, publish_id: str, access_token: str) -> Published:
    return Published(Status.PROCESSING, resume_state={"confirming_since": time.time(), "polls": 0})


def _url_of(post_ids: tuple[str, ...], access_token: str) -> str:
    if not post_ids:
        return ""
    try:
        username = tiktok.creator_info(access_token).username
    except (PlatformFailure, NeedsFreshToken) as error:
        logger.info("Could not learn the TikTok username for the post link: %s", error.__class__.__name__)
        return ""
    return tiktok.post_url(username, post_ids[0]) if username else ""


def confirm(target: PublicationTarget, access_token: str) -> Published | None:
    result = tiktok.publish_status(access_token, target.uploaded_media_id)
    if result.is_failed:
        raise tiktok.failure_of(result.fail_reason)
    if not result.is_complete:
        return None
    return Published(Status.COMPLETED, _url_of(result.post_ids, access_token))
