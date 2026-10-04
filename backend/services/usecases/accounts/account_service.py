import logging

from platforms.core import AuthProfile, AuthToken, PlatformError, PlatformRegistry, PlatformType

from ...core.ports import AccountRepository, Clock

logger = logging.getLogger(__name__)


class AccountService:
    def __init__(self, accounts: AccountRepository, platforms: PlatformRegistry, clock: Clock):
        self._accounts = accounts
        self._platforms = platforms
        self._clock = clock

    async def save(self, owner_id: int, platform: PlatformType, token: AuthToken, profile: AuthProfile) -> int:
        now = self._clock.now()
        account_id = await self._accounts.upsert_connected_account(owner_id, platform, token, profile, now)
        logger.info("Connected %s account %s for user %s", platform, account_id, owner_id)
        return account_id

    async def disconnect(self, account_id: int) -> None:
        account = await self._accounts.get_account_tokens(account_id)
        if account.access_token or account.refresh_token:
            authorization = self._platforms.get(account.platform).get_authorization_interactor()
            try:
                await authorization.revoke_auth_token(account.stored_token())
            except PlatformError as error:
                logger.info("Revoking %s account %s failed: %s", account.platform, account_id, error.message)

        await self._accounts.clear_tokens_and_mark_revoked(account_id)
        logger.info("Disconnected %s account %s", account.platform, account_id)
