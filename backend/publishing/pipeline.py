import logging
from datetime import timedelta

from django.db.models import Q, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from media import storage
from platforms.http import AUTHENTICATION, FILE, NETWORK, UNKNOWN, VALIDATION, PlatformFailure
from platforms.oauth import ProviderError
from social import services as social_services

from .models import PublicationTarget
from .publishers import NeedsFreshToken, UploadCancelled, publisher_for

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
    if isinstance(exception, NeedsFreshToken):
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


def _cancel_requested(target: PublicationTarget) -> bool:
    return PublicationTarget.objects.filter(pk=target.pk, cancel_requested=True).exists()


def _check_cancelled(target: PublicationTarget) -> None:
    if _cancel_requested(target):
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
    result = publisher_for(target.platform).validate(target)
    if not result.valid:
        raise PlatformFailure(VALIDATION, "; ".join(result.errors), details=",".join(result.errors))

    asset = target.publication.asset
    if not storage.absolute(asset.storage_path).exists():
        raise FileNotFoundError(asset.storage_path)


def _progress_recorder(target: PublicationTarget):
    last_written = [0]

    def on_progress(uploaded: int, total: int, state) -> None:
        percent = 100 if total == 0 else int(uploaded * 100 / total)
        if percent == last_written[0]:
            return
        last_written[0] = percent
        _set(target, progress=percent, uploaded_bytes=uploaded, resume_state=state)

    return on_progress


def _upload(target: PublicationTarget) -> str:
    if target.uploaded_media_id:
        return target.uploaded_media_id

    asset = target.publication.asset
    publisher = publisher_for(target.platform)

    _set(target, status=Status.UPLOADING, total_bytes=asset.size_bytes)

    def send(access_token: str, resume: dict | None) -> str:
        return publisher.upload(
            target,
            access_token,
            resume,
            on_progress=_progress_recorder(target),
            should_cancel=lambda: _cancel_requested(target),
        )

    try:
        token = social_services.get_valid_access_token(target.social_account)
        media_id = send(token, target.resume_state)
    except UploadCancelled as cancelled:
        _set(target, resume_state=cancelled.state)
        raise Cancelled() from None
    except NeedsFreshToken as stale:
        logger.info("Target %s: refreshing the token and resuming", target.pk)
        _set(target, resume_state=stale.state)
        fresh = social_services.refresh_access_token(target.social_account)
        media_id = send(fresh, stale.state)

    _set(target, uploaded_media_id=media_id, progress=100, uploaded_bytes=asset.size_bytes)
    return media_id


def _publish(target: PublicationTarget, media_id: str) -> str:
    _check_cancelled(target)
    _set(target, status=Status.PUBLISHING)

    token = social_services.get_valid_access_token(target.social_account)
    published = publisher_for(target.platform).publish(target, media_id, token)

    _set(
        target,
        status=published.status,
        published_url=published.url,
        resume_state=None,
        finished_at=timezone.now(),
    )
    logger.info("Target %s ended as %s", target.pk, published.status)
    return published.status
