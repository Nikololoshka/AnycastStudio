from abc import ABC, abstractmethod

from .platform import Platform
from .platform_type import PlatformType


class PlatformRegistry(ABC):
    @abstractmethod
    def get(self, platform_type: PlatformType) -> Platform: ...

    @abstractmethod
    def all(self) -> tuple[Platform, ...]: ...

    def deferring_upload(self) -> tuple[PlatformType, ...]:
        return tuple(platform.platform_type for platform in self.all() if platform.capabilities.defers_upload)
