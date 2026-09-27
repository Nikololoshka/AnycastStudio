"""Turning a granted authorisation into a stored account, and keeping it usable."""

import logging

from django.db import transaction
from django.utils import timezone

from common.encryption import current_key_version
from platforms.oauth import Identity, ProviderError, TokenBundle

from .models import SocialAccount
from .providers import PROVIDERS

logger = logging.getLogger(__name__)


def _expires_at(bundle: TokenBundle):
    if not bundle.expires_in:
        return None
    return timezone.now() + timezone.timedelta(seconds=int(bundle.expires_in))


def save_account(user, platform: str, bundle: TokenBundle, identity: Identity) -> SocialAccount:
    """Store a freshly authorised account, replacing an earlier connection of the same one."""
    account, _ = SocialAccount.objects.update_or_create(
        user=user,
        platform=platform,
        external_id=identity.external_id,
        defaults={
            "display_name": identity.display_name,
            "avatar_url": identity.avatar_url,
            "access_token": bundle.access_token,
            "refresh_token": bundle.refresh_token or "",
            "key_version": current_key_version(),
            "token_expires_at": _expires_at(bundle),
            "scopes": list(bundle.scopes),
            "extra": identity.extra,
            "status": SocialAccount.Status.ACTIVE,
            "last_error": "",
            "connected_at": timezone.now(),
        },
    )
    logger.info("Connected %s account %s for user %s", platform, account.pk, user.pk)
    return account


def get_valid_access_token(account: SocialAccount) -> str:
    """Return a token that is good right now, refreshing it first if it is not.

    The row is locked for the refresh: two workers refreshing at once would
    race, and on a platform that rotates refresh tokens the loser's token is
    already dead.

    A failure is recorded after the transaction ends, not inside it. Marking the
    account inside would be rolled back by the very exception that reports the
    failure, and the account would stay `active` while being unusable.
    """
    if not account.needs_refresh:
        return account.access_token

    provider = PROVIDERS[account.platform]
    failure: str | None = None

    with transaction.atomic():
        locked = SocialAccount.objects.select_for_update().get(pk=account.pk)
        if not locked.needs_refresh:
            account.refresh_from_db()
            return locked.access_token

        if not locked.refresh_token:
            failure = "No refresh token stored"
        else:
            previous = TokenBundle(
                access_token=locked.access_token,
                refresh_token=locked.refresh_token,
                scopes=tuple(locked.scopes),
            )
            try:
                bundle = provider.refresh(locked.refresh_token).merged_with(previous)
            except ProviderError as error:
                failure = error.message
            else:
                locked.access_token = bundle.access_token
                locked.refresh_token = bundle.refresh_token or ""
                locked.key_version = current_key_version()
                locked.token_expires_at = _expires_at(bundle)
                locked.last_refresh_at = timezone.now()
                locked.status = SocialAccount.Status.ACTIVE
                locked.last_error = ""
                locked.save(
                    update_fields=[
                        "access_token",
                        "refresh_token",
                        "key_version",
                        "token_expires_at",
                        "last_refresh_at",
                        "status",
                        "last_error",
                    ]
                )
                logger.info("Refreshed the token of %s account %s", locked.platform, locked.pk)
                account.refresh_from_db()
                return locked.access_token

    _mark_needs_reauth(account, failure)
    raise ProviderError("This account must be reconnected")


def _mark_needs_reauth(account: SocialAccount, reason: str) -> None:
    SocialAccount.objects.filter(pk=account.pk).update(
        status=SocialAccount.Status.NEEDS_REAUTH, last_error=reason[:500]
    )
    account.refresh_from_db()
    logger.info("%s account %s needs reconnecting: %s", account.platform, account.pk, reason)


def disconnect(account: SocialAccount) -> None:
    """Revoke at the platform if we can, then forget the tokens either way."""
    provider = PROVIDERS.get(account.platform)
    if provider is not None and account.refresh_token:
        try:
            provider.revoke(account.refresh_token)
        except ProviderError as error:
            logger.info("Revoking %s account %s failed: %s", account.platform, account.pk, error.message)

    account.delete()
