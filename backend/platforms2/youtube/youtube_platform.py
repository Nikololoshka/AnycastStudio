from typing import override

import aiohttp

from platforms2.core import AuthorizationInteractor, Platform, PlatformType, PublishInteractor

from .auth import YouTubeAuthorizationInteractor
from .core import GoogleHttp, YouTubeConfig
from .publish import YouTubePublishInteractor
from .youtube_capabilities import YouTubeCapabilities
from .youtube_validator import YouTubeValidator


class YouTubePlatform(Platform):
    platform_type = PlatformType.YOUTUBE

    def __init__(self, config: YouTubeConfig, session: aiohttp.ClientSession):
        http = GoogleHttp(session)

        self.capabilities = YouTubeCapabilities()
        self.validator = YouTubeValidator(self.capabilities)
        self._authorization = YouTubeAuthorizationInteractor(config, http)
        self._publishing = YouTubePublishInteractor(config)

    @override
    def get_authorization_interactor(self) -> AuthorizationInteractor:
        return self._authorization

    @override
    def get_publish_interactor(self) -> PublishInteractor:
        return self._publishing
