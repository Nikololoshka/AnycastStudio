from typing import override

import aiohttp

from platforms2.core import AuthorizationInteractor, Platform, PublishInteractor

from .auth import TikTokAuthorizationInteractor
from .publish import TikTokPublishInteractor
from .tiktok_capabilities import TikTokCapabilities
from .tiktok_config import TikTokConfig
from .tiktok_http import TikTokHttp
from .tiktok_validator import TikTokValidator


class TikTokPlatform(Platform):

    def __init__(self, config: TikTokConfig, session: aiohttp.ClientSession):
        http = TikTokHttp(session)

        self.capabilities = TikTokCapabilities()
        self.validator = TikTokValidator()
        self._authorization = TikTokAuthorizationInteractor(config, http)
        self._publishing = TikTokPublishInteractor(config, http)

    @override
    def get_authorization_interactor(self) -> AuthorizationInteractor:
        return self._authorization

    @override
    def get_publish_interactor(self) -> PublishInteractor:
        return self._publishing
