import logging

from celery import shared_task

from . import services
from .models import UploadSession

logger = logging.getLogger(__name__)


def sweep_upload_sessions() -> int:
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


def sweep_unused_assets() -> int:
    count = 0
    for asset in services.unused_assets():
        services.delete_asset(asset)
        count += 1

    if count:
        logger.info("Swept %d unused media assets", count)
    return count


@shared_task(name="media.sweep_upload_sessions")
def sweep_upload_sessions_task() -> int:
    return sweep_upload_sessions()


@shared_task(name="media.sweep_unused_assets")
def sweep_unused_assets_task() -> int:
    return sweep_unused_assets()
