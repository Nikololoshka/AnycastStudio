import aiohttp

from .core import Platform, PlatformCapabilities, PlatformType
from .core.platform_registry import PlatformRegistry
from .instagram import InstagramPlatform
from .platform_configs import PlatformConfigs
from .tiktok import TikTokPlatform
from .x import XPlatform
from .youtube import YouTubePlatform


class PlatformCatalog(PlatformRegistry):

    def __init__(self, configs: PlatformConfigs, session: aiohttp.ClientSession):
        platforms: tuple[Platform, ...] = (
            YouTubePlatform(configs.youtube, session),
            TikTokPlatform(configs.tiktok, session),
            InstagramPlatform(configs.instagram, session),
            XPlatform(configs.x, session),
        )
        self._platforms = {platform.platform_type: platform for platform in platforms}

    @classmethod
    def capabilities_by_platform(cls) -> dict[PlatformType, PlatformCapabilities]:
        platforms = (YouTubePlatform, TikTokPlatform, InstagramPlatform, XPlatform)
        return {platform.platform_type: platform.capabilities for platform in platforms}

    def get(self, platform_type: PlatformType) -> Platform:
        return self._platforms[platform_type]

    def all(self) -> tuple[Platform, ...]:
        return tuple(self._platforms.values())
