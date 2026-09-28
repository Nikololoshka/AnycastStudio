import logging

from platforms import tiktok
from platforms.core.capabilities import ValidationResult
from platforms.core.errors import FailureType, NeedsFreshToken, PlatformError
from platforms.core.publishing import Confirmation, NotReady, PublicationDraft, PublishJob, Published, TargetStatus

from .publisher import AppPublisher

logger = logging.getLogger(__name__)


def creator_refusals(creator: tiktok.CreatorInfo, options: tiktok.VideoOptions, duration_seconds) -> list[str]:
    refusals: list[str] = []
    if options.privacy_level not in creator.privacy_level_options:
        refusals.append("privacyNotOffered")
    limit = creator.max_video_post_duration_sec
    if limit and duration_seconds and duration_seconds > limit:
        refusals.append("videoTooLong")
    return refusals


def _url_of(post_ids: tuple[str, ...], access_token: str) -> str:
    if not post_ids:
        return ""
    try:
        username = tiktok.creator_info(access_token).username
    except (PlatformError, NeedsFreshToken) as error:
        logger.info("Could not learn the TikTok username for the post link: %s", error.__class__.__name__)
        return ""
    return tiktok.post_url(username, post_ids[0]) if username else ""


class TikTokPublisher(AppPublisher):
    platform = tiktok

    def validate(self, draft: PublicationDraft) -> ValidationResult:
        media = draft.media
        return tiktok.validate(
            caption=draft.caption(),
            options=tiktok.video_options_of(draft.settings),
            size_bytes=media.size_bytes,
            mime_type=media.mime_type,
        )

    def _post_info(self, job: PublishJob, options: tiktok.VideoOptions, creator: tiktok.CreatorInfo) -> tiktok.PostInfo:
        return tiktok.PostInfo(
            title=job.draft.caption(),
            privacy_level=options.privacy_level or "",
            disable_comment=options.disable_comment or creator.comment_disabled,
            disable_duet=options.disable_duet or creator.duet_disabled,
            disable_stitch=options.disable_stitch or creator.stitch_disabled,
            brand_content_toggle=options.brand_content_toggle,
            brand_organic_toggle=options.brand_organic_toggle,
            is_aigc=options.is_aigc,
            video_cover_timestamp_ms=options.cover_timestamp_ms,
        )

    def upload(self, job: PublishJob, access_token: str, on_progress, should_cancel) -> str:
        media = job.draft.media
        options = tiktok.video_options_of(job.draft.settings)
        creator = tiktok.creator_info(access_token)
        refusals = creator_refusals(creator, options, media.duration_seconds)
        if refusals:
            raise PlatformError(FailureType.VALIDATION, "; ".join(refusals), details=",".join(refusals))

        return tiktok.upload(
            path=job.video_path,
            size=media.size_bytes,
            mime_type=media.mime_type,
            post_info=self._post_info(job, options, creator),
            access_token=access_token,
            resume=tiktok.ResumeState.of(job.resume_state),
            on_progress=on_progress,
            should_cancel=should_cancel,
        )

    def confirm(self, job: PublishJob, access_token: str) -> Confirmation:
        result = tiktok.fetch_status(access_token, job.uploaded_media_id)
        if result.is_failed:
            raise tiktok.failure_of(result.fail_reason)
        if not result.is_complete:
            return NotReady()
        return Published(TargetStatus.COMPLETED, _url_of(result.post_ids, access_token))
