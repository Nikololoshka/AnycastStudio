from collections.abc import Iterable
from typing import Self

from .core.config import PlatformConfig
from .core.platform import Platform, PlatformCatalog, PlatformFactory
from .core.ports import Clock
from .instagram import InstagramFactory
from .tiktok import TikTokFactory
from .youtube import YouTubeFactory

FACTORIES: tuple[PlatformFactory, ...] = (YouTubeFactory(), TikTokFactory(), InstagramFactory())


class PlatformRegistry(PlatformCatalog):
    def __init__(self, platforms: Iterable[Platform]):
        self._platforms = {platform.name: platform for platform in platforms}

    @classmethod
    def build(cls, config: PlatformConfig, clock: Clock, factories: Iterable[PlatformFactory] = FACTORIES) -> Self:
        return cls(factory.build(config, clock) for factory in factories)

    def get(self, name: str) -> Platform:
        return self._platforms[name]

    def all(self) -> tuple[Platform, ...]:
        return tuple(self._platforms.values())
