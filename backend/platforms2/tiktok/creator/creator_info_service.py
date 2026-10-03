import logging

from platforms2.core import PlatformError, PlatformFailure
from platforms2.core.accounts import AccountRecord, AccountStatus
from platforms2.core.domain import AccountNeedsReauth, Unavailable
from platforms2.core.ports import AccessTokens, Cache

from .tiktok_creator_info import TikTokCreatorInfo

logger = logging.getLogger(__name__)


class CreatorInfoService:
    CACHE_SECONDS = 300
    RECONNECTING_FAILURES = (
        PlatformFailure.TOKEN_REJECTED,
        PlatformFailure.GRANT_REVOKED,
        PlatformFailure.SCOPE_MISSING,
    )

    def __init__(self, creator_info: TikTokCreatorInfo, tokens: AccessTokens, cache: Cache):
        self._creator_info = creator_info
        self._tokens = tokens
        self._cache = cache

    async def info(self, account: AccountRecord) -> dict:
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
