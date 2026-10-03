from typing import override

import aiohttp

from platforms2.core import AuthorizationInteractor, Platform

from .auth import XAuthorizationInteractor
from .x_capabilities import XCapabilities
from .x_config import XConfig
from .x_http import XHttp
from .x_publisher import XPublisher
from .x_validator import XValidator


class XPlatform(Platform):

    def __init__(self, config: XConfig, session: aiohttp.ClientSession):
        http = XHttp(session)

        self.capabilities = XCapabilities()
        self.publisher = XPublisher()
        self.validator = XValidator()
        self._authorization = XAuthorizationInteractor(config, http)

    @override
    def get_authorization_interactor(self) -> AuthorizationInteractor:
        return self._authorization
