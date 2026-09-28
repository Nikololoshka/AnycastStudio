import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from platforms.core.errors import ProviderError

from . import services
from .models import SocialAccount

logger = logging.getLogger(__name__)

REFRESH_AHEAD = timedelta(hours=1)


def refresh_expiring_tokens() -> int:
    due = SocialAccount.objects.filter(
        status=SocialAccount.Status.ACTIVE,
        token_expires_at__isnull=False,
        token_expires_at__lt=timezone.now() + REFRESH_AHEAD,
    )

    refreshed = 0
    for account in due:
        expired_at = account.token_expires_at
        try:
            services.get_valid_access_token(account, margin=REFRESH_AHEAD)
        except ProviderError as error:
            logger.info("Could not refresh account %s: %s", account.pk, error.message)
            continue
        if account.token_expires_at != expired_at:
            refreshed += 1

    if refreshed:
        logger.info("Refreshed %d platform tokens", refreshed)
    return refreshed


@shared_task(name="social.refresh_expiring_tokens")
def refresh_expiring_tokens_task() -> int:
    return refresh_expiring_tokens()
