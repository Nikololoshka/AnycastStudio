from celery import shared_task

from config.wiring import container


@shared_task(name="publishing.run_target", bind=True, max_retries=0)
def run_target(self, target_id: int) -> str:
    return container().run(lambda services: services.pipeline.run(target_id)) or ""


@shared_task(name="publishing.confirm_target")
def confirm_target(target_id: int) -> None:
    container().run(lambda services: services.confirmations.confirm(target_id))


@shared_task(name="publishing.dispatch_due_targets")
def dispatch_due_targets() -> int:
    return container().run(lambda services: services.dispatcher.dispatch())


@shared_task(name="publishing.sweep_abandoned_targets")
def sweep_abandoned_targets() -> int:
    return container().run(lambda services: services.sweeper.sweep())
