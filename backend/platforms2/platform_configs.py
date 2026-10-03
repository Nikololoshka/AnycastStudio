from dataclasses import dataclass

from .instagram import InstagramConfig
from .tiktok import TikTokConfig
from .x import XConfig
from .youtube import YouTubeConfig


@dataclass(frozen=True)
class PlatformConfigs:
    youtube: YouTubeConfig
    tiktok: TikTokConfig
    instagram: InstagramConfig
    x: XConfig
