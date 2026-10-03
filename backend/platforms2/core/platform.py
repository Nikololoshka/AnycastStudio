from abc import ABC, abstractmethod

from .auth import AuthorizationInteractor
from .platform_capabilities import PlatformCapabilities
from .platform_validator import PlatformValidator
from .publish import PublishInteractor


class Platform(ABC):
    capabilities: PlatformCapabilities
    validator: PlatformValidator

    @abstractmethod
    def get_authorization_interactor(self) -> AuthorizationInteractor: ...

    @abstractmethod
    def get_publish_interactor(self) -> PublishInteractor: ...
