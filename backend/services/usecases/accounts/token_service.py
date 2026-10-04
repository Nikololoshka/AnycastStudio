import logging
from datetime import timedelta

from platforms.core import AuthToken, PlatformError, PlatformFailure, PlatformRegistry

from ...core.accounts.account_status import AccountStatus
from ...core.accounts.account_tokens import AccountTokens
from ...core.ports import AccessTokens, AccountRepository, Clock

logger = logging.getLogger(__name__)


class TokenService(AccessTokens):
    REFRESH_MARGIN = timedelta(minutes=5)
    REFRESH_AHEAD = timedelta(hours=1)
    REFRESH_LEASE = timedelta(minutes=2)
    LEASE_POLL_SECONDS = 0.5
    RECONNECT = "This account must be reconnected"
    REVOKING_FAILURES = (PlatformFailure.GRANT_REVOKED, PlatformFailure.SCOPE_MISSING)

    def __init__(self, accounts: AccountRepository, platforms: PlatformRegistry, clock: Clock):
        self._accounts = accounts
        self._platforms = platforms
        self._clock = clock

    async def valid(self, account_id: int) -> str:
        return await self.valid_within(account_id, self.REFRESH_MARGIN)

    async def valid_within(self, account_id: int, margin: timedelta) -> str:
        account = await self._accounts.tokens_of(account_id)
        if not account.expires_within(self._clock.now(), margin):
            return account.access_token
        return await self.refresh(account_id)

    async def refresh(self, account_id: int) -> str:
        account = await self._accounts.tokens_of(account_id)
        lease_until = self._clock.now() + self.REFRESH_LEASE
        if not await self._accounts.claim_refresh_lease(account_id, self._clock.now(), lease_until):
            logger.info("Waiting for another refresh of %s account %s", account.platform, account_id)
            return await self._await_other_refresh(account)

        try:
            token = await self._refreshed_token(account)
            if await self._accounts.store_refreshed(account_id, account.expires_at, token, self._clock.now()):
                logger.info("Refreshed the token of %s account %s", account.platform, account_id)
        finally:
            await self._accounts.release_refresh_lease(account_id, lease_until)

        return (await self._accounts.tokens_of(account_id)).access_token

    async def refresh_expiring(self) -> int:
        refreshed = 0
        for account_id in await self._accounts.expiring_before(self._clock.now() + self.REFRESH_AHEAD):
            expired_at = (await self._accounts.tokens_of(account_id)).expires_at
            try:
                await self.valid_within(account_id, self.REFRESH_AHEAD)
            except PlatformError as error:
                logger.info("Could not refresh account %s: %s (%s)", account_id, error.message, error.failure)
                continue
            if (await self._accounts.tokens_of(account_id)).expires_at != expired_at:
                refreshed += 1

        if refreshed:
            logger.info("Refreshed %d platform tokens", refreshed)
        return refreshed

    async def _refreshed_token(self, account: AccountTokens) -> AuthToken:
        if not account.refresh_token:
            await self._mark_needs_reauth(account, "No refresh token stored")
            raise PlatformError(PlatformFailure.GRANT_REVOKED, self.RECONNECT)

        authorization = self._platforms.get(account.platform).get_authorization_interactor()
        try:
            token = await authorization.refresh_auth_token(account.refresh_token)
        except PlatformError as error:
            if error.failure in self.REVOKING_FAILURES:
                await self._mark_needs_reauth(account, error.message)
                raise PlatformError(error.failure, self.RECONNECT, details=error.message) from None
            if error.failure is PlatformFailure.MISCONFIGURED:
                logger.error("The %s client is misconfigured: %s", account.platform, error.message)
            raise
        return token.merged_with(account.stored_token())

    async def _await_other_refresh(self, account: AccountTokens) -> str:
        expired_at = account.expires_at
        current = account
        for _ in range(int(self.REFRESH_LEASE.total_seconds() / self.LEASE_POLL_SECONDS)):
            await self._clock.sleep(self.LEASE_POLL_SECONDS)
            current = await self._accounts.tokens_of(account.id)
            if current.expires_at != expired_at or current.lease_until is None:
                break

        if current.status != AccountStatus.ACTIVE:
            raise PlatformError(PlatformFailure.GRANT_REVOKED, self.RECONNECT)
        if current.expires_at == expired_at:
            raise PlatformError(PlatformFailure.NETWORK, "Another refresh of this account did not finish")
        return current.access_token

    async def _mark_needs_reauth(self, account: AccountTokens, reason: str) -> None:
        await self._accounts.mark_needs_reauth(account.id, reason)
        logger.info("%s account %s needs reconnecting: %s", account.platform, account.id, reason)
