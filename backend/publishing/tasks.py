import logging

from celery import shared_task

from . import pipeline, schedule

logger = logging.getLogger(__name__)


@shared_task(name="publishing.run_target", bind=True, max_retries=0)
def run_target(self, target_id: int) -> str:
    return pipeline.run_target(target_id)


@shared_task(name="publishing.dispatch_due_targets")
def dispatch_due_targets() -> int:
    due = schedule.take_due_targets()
    for target_id in due:
        run_target.delay(target_id)
    if due:
        logger.info("Dispatched %d targets whose time has come", len(due))
    return len(due)
