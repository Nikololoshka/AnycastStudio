from collections.abc import Iterable

from .core.platform import Platform, PlatformCatalog


class PlatformRegistry(PlatformCatalog):
    def __init__(self, platforms: Iterable[Platform]):
        self._platforms = {platform.name: platform for platform in platforms}

    def get(self, name: str) -> Platform:
        return self._platforms[name]

    def all(self) -> tuple[Platform, ...]:
        return tuple(self._platforms.values())
