from abc import ABC, abstractmethod

from .auth import AuthorizationInteractor
from .platform_capabilities import PlatformCapabilities
from .platform_publisher import PlatformPublisher
from .platform_validator import PlatformValidator


class Platform(ABC):
    capabilities: PlatformCapabilities
    publisher: PlatformPublisher
    validator: PlatformValidator

    @abstractmethod
    def get_authorization_interactor(self) -> AuthorizationInteractor: ...
