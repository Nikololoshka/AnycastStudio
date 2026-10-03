from typing import override

import aiohttp

from platforms.core import AuthorizationInteractor, Platform, PlatformType, PublishInteractor

from .auth import XAuthorizationInteractor
from .core import XConfig, XHttp
from .publish import XPublishInteractor
from .x_capabilities import XCapabilities
from .x_validator import XValidator


class XPlatform(Platform):
    platform_type = PlatformType.X

    def __init__(self, config: XConfig, session: aiohttp.ClientSession):
        http = XHttp(session)

        self.configured = config.configured
        self.capabilities = XCapabilities()
        self.validator = XValidator(self.capabilities)
        self._authorization = XAuthorizationInteractor(config, http)
        self._publishing = XPublishInteractor(config, http)

    @override
    def get_authorization_interactor(self) -> AuthorizationInteractor:
        return self._authorization

    @override
    def get_publish_interactor(self) -> PublishInteractor:
        return self._publishing
