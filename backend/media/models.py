"""Uploaded video, and the chunked transfer that produced it.

The browser sends a large file in pieces, so two things must be tracked: the
transfer, which is temporary and resumable, and the file it results in, which
is kept only as long as something still needs it.
"""

import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class MediaAsset(models.Model):
    class Status(models.TextChoices):
        UPLOADING = "uploading"
        READY = "ready"
        FAILED = "failed"
        DELETED = "deleted"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="media_assets"
    )

    filename = models.CharField(max_length=260)
    mime_type = models.CharField(max_length=100)
    size_bytes = models.BigIntegerField()
    sha256 = models.CharField(max_length=64, blank=True)

    storage_path = models.CharField(max_length=500)

    duration_seconds = models.FloatField(null=True, blank=True)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.READY)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    def __str__(self) -> str:
        return f"{self.filename} ({self.size_bytes} bytes)"

    @property
    def is_stored(self) -> bool:
        return self.status in (self.Status.UPLOADING, self.Status.READY)


class UploadSession(models.Model):
    """One transfer in progress.

    `received_bytes` is the resume point: the browser asks for it after a
    dropped connection and continues from there rather than starting again.
    """

    class Status(models.TextChoices):
        OPEN = "open"
        COMPLETED = "completed"
        ABORTED = "aborted"

    upload_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="upload_sessions"
    )
    asset = models.OneToOneField(
        MediaAsset, on_delete=models.SET_NULL, null=True, blank=True, related_name="upload_session"
    )

    filename = models.CharField(max_length=260)
    mime_type = models.CharField(max_length=100)
    declared_size = models.BigIntegerField()
    declared_sha256 = models.CharField(max_length=64, blank=True)

    received_bytes = models.BigIntegerField(default=0)
    chunk_size = models.PositiveIntegerField(default=0)
    storage_path = models.CharField(max_length=500)

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(default=timezone.now)
    last_activity_at = models.DateTimeField(default=timezone.now, db_index=True)

    def __str__(self) -> str:
        return f"{self.filename} {self.received_bytes}/{self.declared_size}"

    @staticmethod
    def stale_cutoff():
        return timezone.now() - timedelta(hours=settings.UPLOAD_SESSION_TTL_HOURS)

    @property
    def is_stale(self) -> bool:
        return self.last_activity_at < self.stale_cutoff()
