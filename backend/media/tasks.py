"""Periodic clean-up.

These are plain functions so they can be called from a test, a management
command or a scheduler. Celery wraps them when it arrives; nothing here knows
about it.
"""

import logging

from django.conf import settings
from django.utils import timezone

from . import services
from .models import MediaAsset, UploadSession

logger = logging.getLogger(__name__)


def sweep_upload_sessions() -> int:
    """Abort transfers nobody has touched, and free the disk they were holding."""
    stale = UploadSession.objects.filter(
        status=UploadSession.Status.OPEN, last_activity_at__lt=UploadSession.stale_cutoff()
    )
    count = 0
    for session in stale:
        services.abort(session)
        count += 1

    if count:
        logger.info("Swept %d stale upload sessions", count)
    return count


def sweep_orphan_assets() -> int:
    """Delete files that were uploaded but never used.

    Publishing does not exist yet, so every ready asset older than the orphan
    window qualifies. Once publications exist this also has to spare anything a
    publication still refers to.
    """
    cutoff = timezone.now() - timezone.timedelta(hours=settings.ORPHAN_ASSET_TTL_HOURS)
    orphans = MediaAsset.objects.filter(status=MediaAsset.Status.READY, created_at__lt=cutoff)

    count = 0
    for asset in orphans:
        services.delete_asset(asset)
        count += 1

    if count:
        logger.info("Swept %d orphan media assets", count)
    return count
