"""Keeping connections alive without anybody noticing."""

import logging

from celery import shared_task
from django.utils import timezone

from platforms.oauth import ProviderError

from . import services
from .models import SocialAccount

logger = logging.getLogger(__name__)


def refresh_expiring_tokens() -> int:
    """Refresh tokens that are about to expire, so a publication does not have to.

    Doing it here means a person pressing Publish rarely waits for a token
    round-trip, and an account whose access was revoked is marked as needing
    reconnection before they find out the hard way.
    """
    due = SocialAccount.objects.filter(
        status=SocialAccount.Status.ACTIVE,
        token_expires_at__isnull=False,
        token_expires_at__lt=timezone.now() + timezone.timedelta(hours=1),
    )

    refreshed = 0
    for account in due:
        try:
            services.get_valid_access_token(account)
            refreshed += 1
        except ProviderError as error:
            logger.info("Could not refresh account %s: %s", account.pk, error.message)

    if refreshed:
        logger.info("Refreshed %d platform tokens", refreshed)
    return refreshed


@shared_task(name="social.refresh_expiring_tokens")
def refresh_expiring_tokens_task() -> int:
    return refresh_expiring_tokens()
