from abc import ABC, abstractmethod
from dataclasses import dataclass

from .auth import OAuth2Provider
from .capabilities import Capabilities, Scheduling, Validator
from .config import PlatformConfig
from .publishing import Publisher


@dataclass(frozen=True)
class Platform:
    name: str
    label: str
    capabilities: Capabilities
    provider: OAuth2Provider
    publisher: Publisher
    validator: Validator

    @property
    def defers_upload(self) -> bool:
        return self.capabilities.scheduling == Scheduling.DEFERRED_UPLOAD


class PlatformCatalog(ABC):
    @abstractmethod
    def get(self, name: str) -> Platform: ...

    @abstractmethod
    def all(self) -> tuple[Platform, ...]: ...

    def names(self) -> tuple[str, ...]:
        return tuple(platform.name for platform in self.all())

    def deferring_upload(self) -> tuple[str, ...]:
        return tuple(platform.name for platform in self.all() if platform.defers_upload)


class PlatformFactory(ABC):
    @abstractmethod
    def build(self, config: PlatformConfig) -> Platform: ...
