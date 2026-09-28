import logging
from datetime import timedelta

from ..errors import ProviderError
from ..platform import PlatformCatalog
from ..ports import AccessTokens, AccountRepository, Clock
from .account import AccountStatus, AccountTokens
from .tokens import TokenBundle

logger = logging.getLogger(__name__)

RECONNECT = "This account must be reconnected"


class TokenService(AccessTokens):
    REFRESH_MARGIN = timedelta(minutes=5)
    REFRESH_AHEAD = timedelta(hours=1)
    REFRESH_LEASE = timedelta(minutes=2)
    LEASE_POLL_SECONDS = 0.5

    def __init__(self, accounts: AccountRepository, catalog: PlatformCatalog, clock: Clock):
        self._accounts = accounts
        self._catalog = catalog
        self._clock = clock

    def valid(self, account_id: int) -> str:
        return self.valid_within(account_id, self.REFRESH_MARGIN)

    def valid_within(self, account_id: int, margin: timedelta) -> str:
        account = self._accounts.tokens_of(account_id)
        if not account.expires_within(self._clock.now(), margin):
            return account.access_token
        return self.refresh(account_id)

    def refresh(self, account_id: int) -> str:
        account = self._accounts.tokens_of(account_id)
        lease_until = self._clock.now() + self.REFRESH_LEASE
        if not self._accounts.claim_refresh_lease(account_id, self._clock.now(), lease_until):
            logger.info("Waiting for another refresh of %s account %s", account.platform, account_id)
            return self._await_other_refresh(account)

        try:
            bundle = self._refreshed_bundle(account)
            if self._accounts.store_refreshed(account_id, account.expires_at, bundle, self._clock.now()):
                logger.info("Refreshed the token of %s account %s", account.platform, account_id)
        finally:
            self._accounts.release_refresh_lease(account_id, lease_until)

        return self._accounts.tokens_of(account_id).access_token

    def refresh_expiring(self) -> int:
        refreshed = 0
        for account_id in self._accounts.expiring_before(self._clock.now() + self.REFRESH_AHEAD):
            expired_at = self._accounts.tokens_of(account_id).expires_at
            try:
                self.valid_within(account_id, self.REFRESH_AHEAD)
            except ProviderError as error:
                logger.info("Could not refresh account %s: %s", account_id, error.message)
                continue
            if self._accounts.tokens_of(account_id).expires_at != expired_at:
                refreshed += 1

        if refreshed:
            logger.info("Refreshed %d platform tokens", refreshed)
        return refreshed

    def _refreshed_bundle(self, account: AccountTokens) -> TokenBundle:
        if not account.refresh_token:
            self._mark_needs_reauth(account, "No refresh token stored")
            raise ProviderError(RECONNECT)
        provider = self._catalog.get(account.platform).provider
        try:
            return provider.refresh(account.refresh_token).merged_with(account.stored_bundle())
        except ProviderError as error:
            if error.transient:
                raise
            self._mark_needs_reauth(account, error.message)
            raise ProviderError(RECONNECT) from None

    def _await_other_refresh(self, account: AccountTokens) -> str:
        expired_at = account.expires_at
        current = account
        for _ in range(int(self.REFRESH_LEASE.total_seconds() / self.LEASE_POLL_SECONDS)):
            self._clock.sleep(self.LEASE_POLL_SECONDS)
            current = self._accounts.tokens_of(account.id)
            if current.expires_at != expired_at or current.lease_until is None:
                break

        if current.status != AccountStatus.ACTIVE:
            raise ProviderError(RECONNECT)
        if current.expires_at == expired_at:
            raise ProviderError("Another refresh of this account did not finish", transient=True)
        return current.access_token

    def _mark_needs_reauth(self, account: AccountTokens, reason: str) -> None:
        self._accounts.mark_needs_reauth(account.id, reason)
        logger.info("%s account %s needs reconnecting: %s", account.platform, account.id, reason)
