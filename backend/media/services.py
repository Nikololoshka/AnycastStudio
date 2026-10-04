import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Max, Q, Sum
from django.utils import timezone

from . import storage
from .models import MediaAsset, UploadSession

logger = logging.getLogger(__name__)

READ_SIZE = 256 * 1024


class QuotaExceeded(Exception):
    def __init__(self, used: int, limit: int):
        super().__init__("quota exceeded")
        self.used = used
        self.limit = limit


class TooLarge(Exception):
    def __init__(self, limit: int):
        super().__init__("file too large")
        self.limit = limit


class TooManyUploads(Exception):
    def __init__(self, limit: int):
        super().__init__("too many uploads at once")
        self.limit = limit


class OffsetConflict(Exception):
    def __init__(self, offset: int):
        super().__init__("offset conflict")
        self.offset = offset


class MoreBytesThanDeclared(Exception):
    pass


class AlreadyFinished(Exception):
    pass


class ChecksumMismatch(Exception):
    pass


def stored_bytes(user) -> int:
    return (
        MediaAsset.objects.filter(user=user, status=MediaAsset.Status.READY).aggregate(
            total=Sum("size_bytes")
        )["total"]
        or 0
    )


def reserved_bytes(user) -> int:
    return (
        UploadSession.objects.filter(user=user, status=UploadSession.Status.OPEN).aggregate(
            total=Sum("received_bytes")
        )["total"]
        or 0
    )


def check_can_start(user, size_bytes: int) -> None:
    if size_bytes > user.max_media_asset_bytes:
        raise TooLarge(user.max_media_asset_bytes)

    open_sessions = UploadSession.objects.filter(user=user, status=UploadSession.Status.OPEN).count()
    if open_sessions >= user.max_concurrent_uploads:
        raise TooManyUploads(user.max_concurrent_uploads)

    used = stored_bytes(user) + reserved_bytes(user)
    if used + size_bytes > user.max_storage_bytes:
        raise QuotaExceeded(used, user.max_storage_bytes)


def start(user, filename: str, mime_type: str, size_bytes: int, sha256: str) -> UploadSession:
    check_can_start(user, size_bytes)

    session = UploadSession(
        user=user,
        filename=filename,
        mime_type=mime_type,
        declared_size=size_bytes,
        declared_sha256=sha256 or "",
        chunk_size=settings.UPLOAD_CHUNK_BYTES,
    )
    session.storage_path = storage.partial_path(session.upload_id)
    session.save()
    logger.info("Upload %s started: %s (%d bytes)", session.upload_id, filename, size_bytes)
    return session


def _pieces(stream, limit: int):
    remaining = limit
    while remaining > 0 and (piece := stream.read(min(READ_SIZE, remaining))):
        remaining -= len(piece)
        yield piece


def receive_chunk(session: UploadSession, offset: int, stream) -> int:
    if offset != session.received_bytes:
        raise OffsetConflict(session.received_bytes)

    allowed = session.declared_size - offset
    written = storage.write_at(session.storage_path, offset, _pieces(stream, allowed + 1))
    if written > allowed:
        abort(session)
        raise MoreBytesThanDeclared()

    new_offset = offset + written
    advanced = UploadSession.objects.filter(
        pk=session.pk, status=UploadSession.Status.OPEN, received_bytes=offset
    ).update(received_bytes=new_offset, last_activity_at=timezone.now())
    session.refresh_from_db(fields=["received_bytes"])
    if not advanced:
        raise OffsetConflict(session.received_bytes)
    return new_offset


def _claim_for_completion(session: UploadSession) -> bool:
    return bool(
        UploadSession.objects.filter(pk=session.pk, status=UploadSession.Status.OPEN).update(
            status=UploadSession.Status.COMPLETED, last_activity_at=timezone.now()
        )
    )


def complete(session: UploadSession, duration=None, width=None, height=None) -> MediaAsset:
    if not _claim_for_completion(session):
        raise AlreadyFinished()

    checksum = storage.checksum(session.storage_path)
    if session.declared_sha256 and checksum != session.declared_sha256:
        storage.delete(session.storage_path)
        UploadSession.objects.filter(pk=session.pk).update(status=UploadSession.Status.ABORTED)
        raise ChecksumMismatch()

    asset = MediaAsset.objects.create(
        user=session.user,
        filename=session.filename,
        mime_type=session.mime_type,
        size_bytes=session.received_bytes,
        sha256=checksum,
        storage_path="",
        duration_seconds=duration,
        width=width,
        height=height,
    )

    asset.storage_path = storage.asset_path(session.user_id, asset.pk, session.filename)
    storage.move(session.storage_path, asset.storage_path)
    asset.save(update_fields=["storage_path"])

    UploadSession.objects.filter(pk=session.pk).update(asset=asset)
    logger.info("Upload %s completed as asset %s", session.upload_id, asset.pk)
    return asset


def abort(session: UploadSession) -> None:
    storage.delete(session.storage_path)
    UploadSession.objects.filter(pk=session.pk).update(status=UploadSession.Status.ABORTED)
    logger.info("Upload %s aborted", session.upload_id)


def is_in_use(asset: MediaAsset) -> bool:
    return asset.publications.filter(targets__isnull=False, targets__finished_at__isnull=True).exists()


def never_published_since(cutoff):
    return MediaAsset.objects.filter(
        status=MediaAsset.Status.READY, created_at__lt=cutoff, publications__isnull=True
    )


def published_and_done_since(cutoff):
    return (
        MediaAsset.objects.filter(status=MediaAsset.Status.READY, publications__isnull=False)
        .annotate(
            last_finished=Max("publications__targets__finished_at"),
            unfinished=Count(
                "publications__targets", filter=Q(publications__targets__finished_at__isnull=True)
            ),
        )
        .filter(unfinished=0, last_finished__lt=cutoff)
    )


def unused_assets():
    now = timezone.now()
    orphans = never_published_since(now - timedelta(hours=settings.ORPHAN_ASSET_TTL_HOURS))
    retired = published_and_done_since(now - timedelta(hours=settings.MEDIA_RETENTION_HOURS))
    return [*orphans, *retired]


def delete_asset(asset: MediaAsset) -> None:
    storage.delete(asset.storage_path)
    MediaAsset.objects.filter(pk=asset.pk).update(status=MediaAsset.Status.DELETED, storage_path="")
    logger.info("Deleted the file of media asset %s", asset.pk)


def sweep_upload_sessions() -> int:
    stale = UploadSession.objects.filter(
        status=UploadSession.Status.OPEN, last_activity_at__lt=UploadSession.stale_cutoff()
    )
    count = 0
    for session in stale:
        abort(session)
        count += 1

    if count:
        logger.info("Swept %d stale upload sessions", count)
    return count


def sweep_unused_assets() -> int:
    count = 0
    for asset in unused_assets():
        delete_asset(asset)
        count += 1

    if count:
        logger.info("Swept %d unused media assets", count)
    return count
