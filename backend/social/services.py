import logging
import time
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from common.encryption import current_key_version
from platforms.oauth import Identity, ProviderError, TokenBundle

from .models import REFRESH_LEASE, REFRESH_MARGIN, SocialAccount
from .providers import PROVIDERS

logger = logging.getLogger(__name__)

LEASE_POLL_SECONDS = 0.5


def _expires_at(bundle: TokenBundle):
    if not bundle.expires_in:
        return None
    return timezone.now() + timedelta(seconds=int(bundle.expires_in))


def save_account(user, platform: str, bundle: TokenBundle, identity: Identity) -> SocialAccount:
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


def _stored_bundle(account: SocialAccount) -> TokenBundle:
    return TokenBundle(
        access_token=account.access_token,
        refresh_token=account.refresh_token,
        scopes=tuple(account.scopes),
    )


def _refreshed_bundle(account: SocialAccount) -> TokenBundle:
    if not account.refresh_token:
        _mark_needs_reauth(account, "No refresh token stored")
        raise ProviderError("This account must be reconnected")
    try:
        return PROVIDERS[account.platform].refresh(account.refresh_token).merged_with(_stored_bundle(account))
    except ProviderError as error:
        if error.transient:
            raise
        _mark_needs_reauth(account, error.message)
        raise ProviderError("This account must be reconnected") from None


def _store_unless_already_refreshed(account: SocialAccount, bundle: TokenBundle) -> bool:
    return bool(
        SocialAccount.objects.filter(pk=account.pk, token_expires_at=account.token_expires_at).update(
            access_token=bundle.access_token,
            refresh_token=bundle.refresh_token or "",
            key_version=current_key_version(),
            token_expires_at=_expires_at(bundle),
            last_refresh_at=timezone.now(),
            status=SocialAccount.Status.ACTIVE,
            last_error="",
        )
    )


def _claim_refresh_lease(account: SocialAccount):
    now = timezone.now()
    lease_until = now + REFRESH_LEASE
    free = Q(refresh_lease_until__isnull=True) | Q(refresh_lease_until__lt=now)
    if SocialAccount.objects.filter(free, pk=account.pk).update(refresh_lease_until=lease_until):
        return lease_until
    return None


def _release_refresh_lease(account: SocialAccount, lease_until) -> None:
    SocialAccount.objects.filter(pk=account.pk, refresh_lease_until=lease_until).update(refresh_lease_until=None)


def _await_other_refresh(account: SocialAccount) -> str:
    expired_at = account.token_expires_at
    for _ in range(int(REFRESH_LEASE.total_seconds() / LEASE_POLL_SECONDS)):
        time.sleep(LEASE_POLL_SECONDS)
        account.refresh_from_db()
        if account.token_expires_at != expired_at or account.refresh_lease_until is None:
            break

    if account.status != SocialAccount.Status.ACTIVE:
        raise ProviderError("This account must be reconnected")
    if account.token_expires_at == expired_at:
        raise ProviderError("Another refresh of this account did not finish", transient=True)
    return account.access_token


def refresh_access_token(account: SocialAccount) -> str:
    account.refresh_from_db()
    lease_until = _claim_refresh_lease(account)
    if lease_until is None:
        logger.info("Waiting for another refresh of %s account %s", account.platform, account.pk)
        return _await_other_refresh(account)

    try:
        bundle = _refreshed_bundle(account)
        if _store_unless_already_refreshed(account, bundle):
            logger.info("Refreshed the token of %s account %s", account.platform, account.pk)
    finally:
        _release_refresh_lease(account, lease_until)

    account.refresh_from_db()
    return account.access_token


def get_valid_access_token(account: SocialAccount, margin: timedelta = REFRESH_MARGIN) -> str:
    account.refresh_from_db()
    if not account.expires_within(margin):
        return account.access_token
    return refresh_access_token(account)


def _mark_needs_reauth(account: SocialAccount, reason: str) -> None:
    SocialAccount.objects.filter(pk=account.pk).update(
        status=SocialAccount.Status.NEEDS_REAUTH, last_error=reason[:500]
    )
    account.refresh_from_db()
    logger.info("%s account %s needs reconnecting: %s", account.platform, account.pk, reason)


def disconnect(account: SocialAccount) -> None:
    provider = PROVIDERS.get(account.platform)
    if provider is not None and account.refresh_token:
        try:
            provider.revoke(account.refresh_token)
        except ProviderError as error:
            logger.info("Revoking %s account %s failed: %s", account.platform, account.pk, error.message)

    SocialAccount.objects.filter(pk=account.pk).update(
        access_token="",
        refresh_token="",
        token_expires_at=None,
        status=SocialAccount.Status.REVOKED,
        last_error="",
    )
    logger.info("Disconnected %s account %s", account.platform, account.pk)
