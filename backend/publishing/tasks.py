from celery import shared_task

from . import pipeline


@shared_task(name="publishing.run_target", bind=True, max_retries=0)
def run_target(self, target_id: int) -> str:
    return pipeline.run_target(target_id)
