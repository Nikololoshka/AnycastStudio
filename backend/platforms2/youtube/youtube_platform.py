from typing import override

import aiohttp

from platforms2.core import AuthorizationInteractor, Platform, PublishInteractor

from .auth import YouTubeAuthorizationInteractor
from .google_http import GoogleHttp
from .publish import YouTubePublishInteractor
from .youtube_capabilities import YouTubeCapabilities
from .youtube_config import YouTubeConfig
from .youtube_validator import YouTubeValidator


class YouTubePlatform(Platform):

    def __init__(self, config: YouTubeConfig, session: aiohttp.ClientSession):
        http = GoogleHttp(session)

        self.capabilities = YouTubeCapabilities()
        self.validator = YouTubeValidator()
        self._authorization = YouTubeAuthorizationInteractor(config, http)
        self._publishing = YouTubePublishInteractor(config)

    @override
    def get_authorization_interactor(self) -> AuthorizationInteractor:
        return self._authorization

    @override
    def get_publish_interactor(self) -> PublishInteractor:
        return self._publishing
