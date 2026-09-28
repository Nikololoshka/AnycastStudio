import logging

from pydantic import Field

from ...core.auth.account import AccountRecord, AccountStatus
from ...core.errors import AccountNeedsReauth, NeedsFreshToken, PlatformError, ProviderError, Unavailable
from ...core.http import PlatformModel
from ...core.ports import AccessTokens, Cache
from ...core.upload import TokenRejectionGuard
from ..client import API_ROOT, TikTokClient
from ..options import TikTokOptions

CREATOR_INFO_ENDPOINT = f"{API_ROOT}/post/publish/creator_info/query/"

logger = logging.getLogger(__name__)


class CreatorInfo(PlatformModel):
    username: str = Field("", alias="creator_username")
    nickname: str = Field("", alias="creator_nickname")
    avatar_url: str = Field("", alias="creator_avatar_url")
    privacy_level_options: tuple[str, ...] = ()
    comment_disabled: bool = False
    duet_disabled: bool = False
    stitch_disabled: bool = False
    max_video_post_duration_sec: int | None = None

    def as_json(self) -> dict:
        return {
            "username": self.username,
            "nickname": self.nickname,
            "avatarUrl": self.avatar_url,
            "privacyLevelOptions": list(self.privacy_level_options),
            "commentDisabled": self.comment_disabled,
            "duetDisabled": self.duet_disabled,
            "stitchDisabled": self.stitch_disabled,
            "maxVideoPostDurationSec": self.max_video_post_duration_sec,
        }

    def refusals(self, options: TikTokOptions, duration_seconds: float | None) -> list[str]:
        refusals: list[str] = []
        if options.privacy_level not in self.privacy_level_options:
            refusals.append("privacyNotOffered")
        limit = self.max_video_post_duration_sec
        if limit and duration_seconds and duration_seconds > limit:
            refusals.append("videoTooLong")
        return refusals


class CreatorInfoApi:
    def __init__(self, client: TikTokClient):
        self._client = client

    def query(self, access_token: str) -> CreatorInfo:
        return TokenRejectionGuard().run(
            lambda: self._client.call("POST", CREATOR_INFO_ENDPOINT, access_token, CreatorInfo)
        )


class CreatorInfoService:
    CACHE_SECONDS = 300

    def __init__(self, api: CreatorInfoApi, tokens: AccessTokens, cache: Cache):
        self._api = api
        self._tokens = tokens
        self._cache = cache

    def info(self, account: AccountRecord) -> dict:
        if account.status == AccountStatus.NEEDS_REAUTH:
            raise AccountNeedsReauth(account.platform)

        key = f"tiktok-creator-info:{account.id}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        info = self._query(account).as_json()
        self._cache.set(key, info, self.CACHE_SECONDS)
        return info

    def _query(self, account: AccountRecord) -> CreatorInfo:
        try:
            return self._tokens.run(account.id, self._api.query)
        except ProviderError as error:
            if error.transient:
                raise self._unavailable(account, error.message) from None
            raise AccountNeedsReauth(account.platform) from None
        except NeedsFreshToken:
            raise AccountNeedsReauth(account.platform) from None
        except PlatformError as failure:
            raise self._unavailable(account, failure.message) from None

    @staticmethod
    def _unavailable(account: AccountRecord, reason: str) -> Unavailable:
        logger.info("Creator info for account %s failed: %s", account.id, reason)
        return Unavailable("platform_unavailable")
