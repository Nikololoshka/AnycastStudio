from collections.abc import Mapping

import aiohttp

from .core import Platform, PlatformCapabilities, PlatformType
from .core.platform_registry import PlatformRegistry
from .instagram import InstagramPlatform
from .instagram.publish.instagram_options import InstagramOptions
from .platform_configs import PlatformConfigs
from .tiktok import TikTokPlatform
from .tiktok.publish.tiktok_options import TikTokOptions
from .x import XPlatform
from .x.publish.x_options import XOptions
from .youtube import YouTubePlatform
from .youtube.publish.youtube_options import YouTubeOptions


class PlatformCatalog(PlatformRegistry):
    OPTIONS = {
        PlatformType.YOUTUBE: YouTubeOptions,
        PlatformType.TIKTOK: TikTokOptions,
        PlatformType.INSTAGRAM: InstagramOptions,
        PlatformType.X: XOptions,
    }

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

    @classmethod
    def normalized_settings(cls, platform_type: PlatformType, raw: Mapping) -> dict:
        return cls.OPTIONS[platform_type].of(raw).as_json()

    @classmethod
    def is_exact_settings(cls, platform_type: PlatformType, raw: Mapping) -> bool:
        expected = {**cls.normalized_settings(platform_type, {}), **raw}
        normalized = cls.normalized_settings(platform_type, raw)
        return normalized == expected and all(
            isinstance(value, bool) == isinstance(expected[key], bool) for key, value in normalized.items()
        )

    def get(self, platform_type: PlatformType) -> Platform:
        return self._platforms[platform_type]

    def all(self) -> tuple[Platform, ...]:
        return tuple(self._platforms.values())
