from typing import override

import aiohttp

from platforms2.core import AuthorizationInteractor, Platform

from .auth import TikTokAuthorizationInteractor
from .tiktok_capabilities import TikTokCapabilities
from .tiktok_config import TikTokConfig
from .tiktok_http import TikTokHttp
from .tiktok_publisher import TikTokPublisher
from .tiktok_validator import TikTokValidator


class TikTokPlatform(Platform):

    def __init__(self, config: TikTokConfig, session: aiohttp.ClientSession):
        http = TikTokHttp(session)

        self.capabilities = TikTokCapabilities()
        self.publisher = TikTokPublisher()
        self.validator = TikTokValidator()
        self._authorization = TikTokAuthorizationInteractor(config, http)

    @override
    def get_authorization_interactor(self) -> AuthorizationInteractor:
        return self._authorization
