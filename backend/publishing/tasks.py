import logging

from celery import shared_task

from . import pipeline, schedule
from .models import PublicationTarget

logger = logging.getLogger(__name__)


def _confirm_later(target_id: int, delay_seconds: int) -> None:
    confirm_target.apply_async((target_id,), countdown=delay_seconds)


@shared_task(name="publishing.run_target", bind=True, max_retries=0)
def run_target(self, target_id: int) -> str:
    status = pipeline.run_target(target_id)
    if status == PublicationTarget.Status.PROCESSING:
        _confirm_later(target_id, pipeline.POLL_DELAYS_SECONDS[0])
    return status


@shared_task(name="publishing.confirm_target")
def confirm_target(target_id: int) -> None:
    delay_seconds = pipeline.confirm_target(target_id)
    if delay_seconds is not None:
        _confirm_later(target_id, delay_seconds)


@shared_task(name="publishing.dispatch_due_targets")
def dispatch_due_targets() -> int:
    due = schedule.take_due_targets()
    for target_id in due:
        run_target.delay(target_id)
    if due:
        logger.info("Dispatched %d targets whose time has come", len(due))

    stalled = schedule.take_stalled_confirmations()
    for target_id in stalled:
        confirm_target.delay(target_id)
    if stalled:
        logger.info("Resumed confirming %d targets", len(stalled))

    return len(due)
