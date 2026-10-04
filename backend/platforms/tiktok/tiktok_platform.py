from typing import override

import aiohttp

from platforms.core import AuthorizationInteractor, Platform, PlatformType, PublishInteractor

from .auth import TikTokAuthorizationInteractor
from .core import TikTokConfig, TikTokHttp
from .creator import TikTokCreatorInfo
from .publish import TikTokPublishInteractor
from .tiktok_capabilities import TikTokCapabilities
from .tiktok_validator import TikTokValidator


class TikTokPlatform(Platform):
    platform_type = PlatformType.TIKTOK
    capabilities = TikTokCapabilities()

    def __init__(self, config: TikTokConfig, session: aiohttp.ClientSession):
        http = TikTokHttp(session)

        self.configured = config.configured
        self.validator = TikTokValidator(self.capabilities)
        self._authorization = TikTokAuthorizationInteractor(config, http)
        self.creator_info = TikTokCreatorInfo(http)
        self._publishing = TikTokPublishInteractor(config, http, self.creator_info)

    @override
    def get_authorization_interactor(self) -> AuthorizationInteractor:
        return self._authorization

    @override
    def get_publish_interactor(self) -> PublishInteractor:
        return self._publishing
