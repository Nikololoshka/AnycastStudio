import aiohttp

from .core import Platform, PlatformType
from .instagram import InstagramPlatform
from .platform_configs import PlatformConfigs
from .tiktok import TikTokPlatform
from .x import XPlatform
from .youtube import YouTubePlatform


class PlatformCatalog:

    def __init__(self, configs: PlatformConfigs, session: aiohttp.ClientSession):
        platforms = (
            YouTubePlatform(configs.youtube, session),
            TikTokPlatform(configs.tiktok, session),
            InstagramPlatform(configs.instagram, session),
            XPlatform(configs.x, session),
        )
        self._platforms = {platform.platform_type: platform for platform in platforms}

    def get(self, platform_type: PlatformType) -> Platform:
        return self._platforms[platform_type]

    def all(self) -> tuple[Platform, ...]:
        return tuple(self._platforms.values())

    def deferring_upload(self) -> tuple[PlatformType, ...]:
        return tuple(platform.platform_type for platform in self.all() if platform.capabilities.defers_upload)
