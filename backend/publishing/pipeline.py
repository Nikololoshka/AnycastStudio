"""Taking one target from queued to published.

A port of the desktop client's UploadManager. The shape is deliberately the
same — validate, upload, publish, and one failure recorded per target — because
that shape was right; what changed is where the state lives. Redux dispatches
became writes to the target row.

One rule runs through all of it: never hold a database transaction open across
a call to a platform. An upload takes minutes, and on SQLite a transaction held
that long stops everything else from writing.
"""

import logging

from django.utils import timezone

from media import storage
from platforms import youtube
from platforms.http import PlatformFailure
from platforms.oauth import ProviderError
from social import services as social_services

from .models import PublicationTarget

logger = logging.getLogger(__name__)

Status = PublicationTarget.Status


class Cancelled(Exception):
    """The person asked for this target to stop."""


def _set(target: PublicationTarget, **fields) -> None:
    PublicationTarget.objects.filter(pk=target.pk).update(**fields)
    for key, value in fields.items():
        setattr(target, key, value)


def _fail(target: PublicationTarget, error: dict) -> None:
    _set(target, status=Status.FAILED, error=error, finished_at=timezone.now())
    logger.info("Target %s failed: %s", target.pk, error.get("message"))


def _error_of(exception: Exception) -> dict:
    """Map anything that went wrong onto the vocabulary the browser speaks."""
    if isinstance(exception, PlatformFailure):
        return {"type": exception.type, "message": exception.message, "details": exception.details}
    if isinstance(exception, ProviderError):
        return {"type": "authentication", "message": exception.message}
    if isinstance(exception, FileNotFoundError):
        return {"type": "file", "message": "The uploaded video is no longer on the server"}
    return {"type": "unknown", "message": str(exception) or exception.__class__.__name__}


def claim(target_id: int) -> PublicationTarget | None:
    """Take a target for work, or None if somebody already has it.

    A conditional UPDATE rather than a lock: SQLite has no SKIP LOCKED, and the
    pattern is what makes an at-least-once task queue behave as effectively-once.
    """
    claimed = PublicationTarget.objects.filter(pk=target_id, status=Status.QUEUED).update(
        status=Status.VALIDATING, started_at=timezone.now()
    )
    if not claimed:
        return None
    return PublicationTarget.objects.select_related(
        "publication", "publication__asset", "social_account"
    ).get(pk=target_id)


def _check_cancelled(target: PublicationTarget) -> None:
    if PublicationTarget.objects.filter(pk=target.pk, cancel_requested=True).exists():
        raise Cancelled()


def run_target(target_id: int) -> str:
    """Validate, upload and publish one target. Returns the final status."""
    target = claim(target_id)
    if target is None:
        logger.info("Target %s was already taken", target_id)
        return ""

    _set(target, attempt_count=target.attempt_count + 1, error=None)

    try:
        _validate(target)
        video_id = _upload(target)
        return _publish(target, video_id)
    except Cancelled:
        _set(target, status=Status.CANCELLED, finished_at=timezone.now())
        return Status.CANCELLED
    except Exception as exception:  # noqa: BLE001 — every failure belongs on the target
        logger.exception("Target %s raised", target_id)
        _fail(target, _error_of(exception))
        return Status.FAILED


def _validate(target: PublicationTarget) -> None:
    _set(target, status=Status.VALIDATING)
    publication = target.publication
    asset = publication.asset

    result = youtube.validate(
        title=publication.title,
        description=publication.description,
        size_bytes=asset.size_bytes,
        mime_type=asset.mime_type,
    )
    if not result.valid:
        raise PlatformFailure("validation", "; ".join(result.errors), details=",".join(result.errors))

    if not storage.absolute(asset.storage_path).exists():
        raise FileNotFoundError(asset.storage_path)


def _metadata(target: PublicationTarget, options: youtube.VideoOptions) -> youtube.VideoMetadata:
    publication = target.publication
    return youtube.VideoMetadata(
        title=publication.title,
        description=youtube.description_with_hashtags(
            publication.description, list(publication.hashtags), options
        ),
        tags=list(publication.hashtags),
        # Scheduled videos must go up private, or YouTube ignores publishAt.
        privacy_status="private" if publication.publish_at else options.privacy_status,
        category_id=options.category_id,
        license=options.license,
        embeddable=options.embeddable,
        public_stats_viewable=options.public_stats_viewable,
        made_for_kids=options.made_for_kids,
        contains_synthetic_media=options.contains_synthetic_media,
        notify_subscribers=options.notify_subscribers,
    )


def _upload(target: PublicationTarget) -> str:
    if target.uploaded_media_id:
        return target.uploaded_media_id  # a retry after the bytes already landed

    asset = target.publication.asset
    options = youtube.video_options_of(target.settings)

    _set(target, status=Status.UPLOADING, total_bytes=asset.size_bytes)

    last_written = [0]

    def on_progress(uploaded: int, total: int, state) -> None:
        percent = 100 if total == 0 else int(uploaded * 100 / total)
        # Throttled to whole percents: the upload loop reports far more often
        # than that, and every write is a write to the shared database file.
        if percent == last_written[0]:
            return
        last_written[0] = percent
        _set(
            target,
            progress=percent,
            uploaded_bytes=uploaded,
            resume_state=state.as_dict(),
        )

    def should_cancel() -> bool:
        return PublicationTarget.objects.filter(pk=target.pk, cancel_requested=True).exists()

    token = social_services.get_valid_access_token(target.social_account)
    resume = youtube.ResumeState.of(target.resume_state)

    try:
        video_id = youtube.upload(
            path=storage.absolute(asset.storage_path),
            size=asset.size_bytes,
            mime_type=asset.mime_type,
            metadata=_metadata(target, options),
            access_token=token,
            resume=resume,
            on_progress=on_progress,
            should_cancel=should_cancel,
        )
    except youtube.UploadCancelled as cancelled:
        _set(target, resume_state=cancelled.state.as_dict())
        raise Cancelled() from None
    except youtube.NeedsFreshToken as stale:
        # The token died mid-upload. Everything already sent is still on
        # Google's side, so refresh and carry on from the confirmed offset
        # rather than starting the file again.
        logger.info("Target %s: refreshing the token and resuming", target.pk)
        _set(target, resume_state=stale.state.as_dict())
        target.social_account.refresh_from_db()
        fresh = social_services.get_valid_access_token(target.social_account)
        video_id = youtube.upload(
            path=storage.absolute(asset.storage_path),
            size=asset.size_bytes,
            mime_type=asset.mime_type,
            metadata=_metadata(target, options),
            access_token=fresh,
            resume=stale.state,
            on_progress=on_progress,
            should_cancel=should_cancel,
        )

    _set(target, uploaded_media_id=video_id, progress=100, uploaded_bytes=asset.size_bytes)
    return video_id


def _publish(target: PublicationTarget, video_id: str) -> str:
    _check_cancelled(target)
    _set(target, status=Status.PUBLISHING)

    options = youtube.video_options_of(target.settings)
    token = social_services.get_valid_access_token(target.social_account)
    publish_at = target.publication.publish_at

    if publish_at:
        url = youtube.schedule(video_id, token, options, publish_at.isoformat())
        _set(
            target,
            status=Status.SCHEDULED,
            published_url=url,
            resume_state=None,
            finished_at=timezone.now(),
        )
        logger.info("Target %s scheduled for %s", target.pk, publish_at.isoformat())
        return Status.SCHEDULED

    url = youtube.publish(video_id, token, options)
    _set(
        target,
        status=Status.COMPLETED,
        published_url=url,
        resume_state=None,
        finished_at=timezone.now(),
    )
    logger.info("Target %s published at %s", target.pk, url)
    return Status.COMPLETED
