from celery import shared_task

from . import pipeline


@shared_task(name="publishing.run_target", bind=True, max_retries=0)
def run_target(self, target_id: int) -> str:
    """Publish one target.

    No Celery-level retry: the pipeline already retries what is worth
    retrying, and repeating a rejected upload burns YouTube quota that the
    person cannot get back. A failed target is retried when somebody asks.
    """
    return pipeline.run_target(target_id)
