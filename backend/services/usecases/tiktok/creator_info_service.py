import logging

from platforms.core import PlatformError, PlatformFailure, PlatformType
from platforms.tiktok.creator import TikTokCreatorInfo

from ...core.accounts import AccountStatus
from ...core.domain import AccountNeedsReauth, NotFound, Unavailable
from ...core.ports import AccessTokens, AccountRepository, Cache

logger = logging.getLogger(__name__)


class CreatorInfoService:
    CACHE_SECONDS = 300
    RECONNECTING_FAILURES = (
        PlatformFailure.TOKEN_REJECTED,
        PlatformFailure.GRANT_REVOKED,
        PlatformFailure.SCOPE_MISSING,
    )

    def __init__(
        self, accounts: AccountRepository, creator_info: TikTokCreatorInfo, tokens: AccessTokens, cache: Cache
    ):
        self._accounts = accounts
        self._creator_info = creator_info
        self._tokens = tokens
        self._cache = cache

    async def info(self, owner_id: int, account_id: int) -> dict:
        account = await self._accounts.get_connected_account(owner_id, account_id)
        if account.platform is not PlatformType.TIKTOK:
            raise NotFound()
        if account.status == AccountStatus.NEEDS_REAUTH:
            raise AccountNeedsReauth(account.platform)

        key = f"tiktok-creator-info:{account.id}"
        cached = await self._cache.get(key)
        if cached is not None:
            return cached

        try:
            creator = await self._tokens.run(account.id, self._creator_info.fetch)
        except PlatformError as error:
            if error.failure in self.RECONNECTING_FAILURES:
                raise AccountNeedsReauth(account.platform) from None
            logger.info("Creator info for account %s failed: %s (%s)", account.id, error.message, error.failure)
            raise Unavailable("platform_unavailable") from None

        info = creator.as_json()
        await self._cache.set(key, info, self.CACHE_SECONDS)
        return info
