from collections.abc import Iterable
from typing import Self

from .core.config import PlatformConfig
from .core.platform import Platform, PlatformCatalog, PlatformFactory
from .youtube import YouTubeFactory

FACTORIES: tuple[PlatformFactory, ...] = (YouTubeFactory(),)


class PlatformRegistry(PlatformCatalog):
    def __init__(self, platforms: Iterable[Platform]):
        self._platforms = {platform.name: platform for platform in platforms}

    @classmethod
    def build(cls, config: PlatformConfig, factories: Iterable[PlatformFactory] = FACTORIES) -> Self:
        return cls(factory.build(config) for factory in factories)

    def get(self, name: str) -> Platform:
        return self._platforms[name]

    def all(self) -> tuple[Platform, ...]:
        return tuple(self._platforms.values())
