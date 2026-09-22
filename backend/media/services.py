"""Quotas and the rules around finishing a transfer."""

import logging

from django.conf import settings
from django.db.models import Sum
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


def stored_bytes(user) -> int:
    return (
        MediaAsset.objects.filter(
            user=user, status__in=[MediaAsset.Status.UPLOADING, MediaAsset.Status.READY]
        ).aggregate(total=Sum("size_bytes"))["total"]
        or 0
    )


def check_can_start(user, size_bytes: int) -> None:
    """Refuse before a single byte is transferred, not after four gigabytes."""
    quota = user.quota

    if size_bytes > quota.max_media_asset_bytes:
        raise TooLarge(quota.max_media_asset_bytes)

    open_sessions = UploadSession.objects.filter(user=user, status=UploadSession.Status.OPEN).count()
    if open_sessions >= quota.max_concurrent_uploads:
        raise TooManyUploads(quota.max_concurrent_uploads)

    used = stored_bytes(user) + reserved_bytes(user)
    if used + size_bytes > quota.max_storage_bytes:
        raise QuotaExceeded(used, quota.max_storage_bytes)


def reserved_bytes(user) -> int:
    """What open transfers have already written. Counted against the quota so a
    person cannot start ten uploads that only together exceed it."""
    return (
        UploadSession.objects.filter(user=user, status=UploadSession.Status.OPEN).aggregate(
            total=Sum("received_bytes")
        )["total"]
        or 0
    )


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


def receive_chunk(session: UploadSession, stream) -> int:
    """Append the request body to the partial file and return the new offset.

    The stream is read in pieces rather than through request.body: a chunk is
    megabytes, and buffering it in Python only to write it out again doubles the
    memory for nothing.
    """
    written = 0
    while chunk := stream.read(READ_SIZE):
        storage.append(session.storage_path, chunk)
        written += len(chunk)

    offset = storage.size(session.storage_path)
    UploadSession.objects.filter(pk=session.pk).update(
        received_bytes=offset, last_activity_at=timezone.now()
    )
    session.received_bytes = offset
    return offset


def complete(session: UploadSession, duration=None, width=None, height=None) -> MediaAsset:
    """Verify what arrived, then turn it into an asset the person owns."""
    checksum = storage.checksum(session.storage_path)
    if session.declared_sha256 and checksum != session.declared_sha256:
        raise ValueError("checksum_mismatch")

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
        status=MediaAsset.Status.READY,
    )

    asset.storage_path = storage.asset_path(session.user_id, asset.pk, session.filename)
    storage.move(session.storage_path, asset.storage_path)
    asset.save(update_fields=["storage_path"])

    UploadSession.objects.filter(pk=session.pk).update(
        status=UploadSession.Status.COMPLETED, asset=asset, last_activity_at=timezone.now()
    )
    logger.info("Upload %s completed as asset %s", session.upload_id, asset.pk)
    return asset


def abort(session: UploadSession) -> None:
    storage.delete(session.storage_path)
    UploadSession.objects.filter(pk=session.pk).update(status=UploadSession.Status.ABORTED)
    logger.info("Upload %s aborted", session.upload_id)


def delete_asset(asset: MediaAsset) -> None:
    storage.delete(asset.storage_path)
    MediaAsset.objects.filter(pk=asset.pk).update(status=MediaAsset.Status.DELETED, storage_path="")
