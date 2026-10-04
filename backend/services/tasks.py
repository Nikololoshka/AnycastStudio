from celery import shared_task

from media import services as media

from .wiring import container


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


@shared_task(name="social.refresh_expiring_tokens")
def refresh_expiring_tokens() -> int:
    return container().run(lambda services: services.tokens.refresh_expiring())


@shared_task(name="media.sweep_upload_sessions")
def sweep_upload_sessions() -> int:
    return media.sweep_upload_sessions()


@shared_task(name="media.sweep_unused_assets")
def sweep_unused_assets() -> int:
    return media.sweep_unused_assets()
