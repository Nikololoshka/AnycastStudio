from celery import shared_task

from config.wiring import container


@shared_task(name="social.refresh_expiring_tokens")
def refresh_expiring_tokens_task() -> int:
    return container().run(lambda services: services.tokens.refresh_expiring())
