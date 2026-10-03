from typing import override

import aiohttp

from platforms.core import AuthorizationInteractor, Platform, PlatformType, PublishInteractor

from .auth import InstagramAuthorizationInteractor
from .core import InstagramConfig, InstagramHttp
from .instagram_capabilities import InstagramCapabilities
from .instagram_validator import InstagramValidator
from .publish import InstagramPublishInteractor


class InstagramPlatform(Platform):
    platform_type = PlatformType.INSTAGRAM

    def __init__(self, config: InstagramConfig, session: aiohttp.ClientSession):
        http = InstagramHttp(session)

        self.configured = config.configured
        self.capabilities = InstagramCapabilities()
        self.validator = InstagramValidator(self.capabilities)
        self._authorization = InstagramAuthorizationInteractor(config, http)
        self._publishing = InstagramPublishInteractor(config, http)

    @override
    def get_authorization_interactor(self) -> AuthorizationInteractor:
        return self._authorization

    @override
    def get_publish_interactor(self) -> PublishInteractor:
        return self._publishing
