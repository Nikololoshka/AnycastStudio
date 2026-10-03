from typing import override

import aiohttp

from platforms2.core import AuthorizationInteractor, Platform

from .auth import InstagramAuthorizationInteractor
from .instagram_capabilities import InstagramCapabilities
from .instagram_config import InstagramConfig
from .instagram_http import InstagramHttp
from .instagram_publisher import InstagramPublisher
from .instagram_validator import InstagramValidator


class InstagramPlatform(Platform):

    def __init__(self, config: InstagramConfig, session: aiohttp.ClientSession):
        http = InstagramHttp(session)

        self.capabilities = InstagramCapabilities()
        self.publisher = InstagramPublisher()
        self.validator = InstagramValidator()
        self._authorization = InstagramAuthorizationInteractor(config, http)

    @override
    def get_authorization_interactor(self) -> AuthorizationInteractor:
        return self._authorization
