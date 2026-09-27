import logging
from datetime import timedelta

from django.db.models import Q, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from media import storage
from platforms import youtube
from platforms.http import AUTHENTICATION, FILE, NETWORK, UNKNOWN, VALIDATION, PlatformFailure
from platforms.oauth import ProviderError
from social import services as social_services

from .models import PublicationTarget

logger = logging.getLogger(__name__)

Status = PublicationTarget.Status

ABANDONED_AFTER = timedelta(minutes=15)


class Cancelled(Exception):
    pass


def _set(target: PublicationTarget, **fields) -> None:
    fields["last_activity_at"] = timezone.now()
    PublicationTarget.objects.filter(pk=target.pk).update(**fields)
    for key, value in fields.items():
        setattr(target, key, value)


def _fail(target: PublicationTarget, error: dict) -> None:
    _set(target, status=Status.FAILED, error=error, finished_at=timezone.now())
    logger.info("Target %s failed: %s", target.pk, error.get("message"))


def _error_of(exception: Exception) -> dict:
    if isinstance(exception, PlatformFailure):
        return {"type": exception.type, "message": exception.message, "details": exception.details}
    if isinstance(exception, ProviderError):
        return {"type": NETWORK if exception.transient else AUTHENTICATION, "message": exception.message}
    if isinstance(exception, youtube.NeedsFreshToken):
        return {"type": AUTHENTICATION, "message": str(exception)}
    if isinstance(exception, FileNotFoundError):
        return {"type": FILE, "message": "The uploaded video is no longer on the server"}
    return {"type": UNKNOWN, "message": str(exception) or exception.__class__.__name__}


def _claimable():
    queued = Q(status=Status.QUEUED)
    abandoned = Q(status__in=PublicationTarget.RUNNING, last_activity_at__lt=timezone.now() - ABANDONED_AFTER)
    return queued | abandoned


def claim(target_id: int) -> PublicationTarget | None:
    now = timezone.now()
    claimed = PublicationTarget.objects.filter(_claimable(), pk=target_id).update(
        status=Status.VALIDATING,
        started_at=Coalesce("started_at", Value(now)),
        last_activity_at=now,
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
    target = claim(target_id)
    if target is None:
        logger.info("Target %s was already taken", target_id)
        return ""

    _set(target, attempt_count=target.attempt_count + 1, error=None)

    try:
        _check_cancelled(target)
        _validate(target)
        video_id = _upload(target)
        return _publish(target, video_id)
    except Cancelled:
        _set(target, status=Status.CANCELLED, finished_at=timezone.now())
        return Status.CANCELLED
    except Exception as exception:
        logger.exception("Target %s raised", target_id)
        _fail(target, _error_of(exception))
        return Status.FAILED


def _validate(target: PublicationTarget) -> None:
    publication = target.publication
    asset = publication.asset

    result = youtube.validate(
        title=publication.title,
        description=publication.description,
        size_bytes=asset.size_bytes,
        mime_type=asset.mime_type,
    )
    if not result.valid:
        raise PlatformFailure(VALIDATION, "; ".join(result.errors), details=",".join(result.errors))

    if not storage.absolute(asset.storage_path).exists():
        raise FileNotFoundError(asset.storage_path)


def _privacy_at_upload(target: PublicationTarget, options: youtube.VideoOptions) -> str:
    return "private" if target.publication.publish_at else options.privacy_status


def _metadata(target: PublicationTarget, options: youtube.VideoOptions) -> youtube.VideoMetadata:
    publication = target.publication
    return youtube.VideoMetadata(
        title=publication.title,
        description=youtube.description_with_hashtags(
            publication.description, list(publication.hashtags), options
        ),
        tags=list(publication.hashtags),
        privacy_status=_privacy_at_upload(target, options),
        category_id=options.category_id,
        license=options.license,
        embeddable=options.embeddable,
        public_stats_viewable=options.public_stats_viewable,
        made_for_kids=options.made_for_kids,
        contains_synthetic_media=options.contains_synthetic_media,
        notify_subscribers=options.notify_subscribers,
    )


def _progress_recorder(target: PublicationTarget):
    last_written = [0]

    def on_progress(uploaded: int, total: int, state) -> None:
        percent = 100 if total == 0 else int(uploaded * 100 / total)
        if percent == last_written[0]:
            return
        last_written[0] = percent
        _set(target, progress=percent, uploaded_bytes=uploaded, resume_state=state.as_dict())

    return on_progress


def _upload(target: PublicationTarget) -> str:
    if target.uploaded_media_id:
        return target.uploaded_media_id

    asset = target.publication.asset
    options = youtube.video_options_of(target.settings)

    _set(target, status=Status.UPLOADING, total_bytes=asset.size_bytes)

    def send(access_token: str, resume):
        return youtube.upload(
            path=storage.absolute(asset.storage_path),
            size=asset.size_bytes,
            mime_type=asset.mime_type,
            metadata=_metadata(target, options),
            access_token=access_token,
            resume=resume,
            on_progress=_progress_recorder(target),
            should_cancel=lambda: PublicationTarget.objects.filter(pk=target.pk, cancel_requested=True).exists(),
        )

    try:
        token = social_services.get_valid_access_token(target.social_account)
        video_id = send(token, youtube.ResumeState.of(target.resume_state))
    except youtube.UploadCancelled as cancelled:
        _set(target, resume_state=cancelled.state.as_dict())
        raise Cancelled() from None
    except youtube.NeedsFreshToken as stale:
        logger.info("Target %s: refreshing the token and resuming", target.pk)
        _set(target, resume_state=stale.state.as_dict())
        fresh = social_services.refresh_access_token(target.social_account)
        video_id = send(fresh, stale.state)

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
        _set(target, status=Status.SCHEDULED, published_url=url, resume_state=None, finished_at=timezone.now())
        logger.info("Target %s scheduled for %s", target.pk, publish_at.isoformat())
        return Status.SCHEDULED

    url = youtube.publish(video_id, token, options)
    _set(target, status=Status.COMPLETED, published_url=url, resume_state=None, finished_at=timezone.now())
    logger.info("Target %s published at %s", target.pk, url)
    return Status.COMPLETED
