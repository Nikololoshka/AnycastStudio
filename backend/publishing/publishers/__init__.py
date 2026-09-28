from .instagram import InstagramPublisher
from .publisher import AppPublisher
from .tiktok import TikTokPublisher
from .x import XPublisher
from .youtube import YouTubePublisher

PUBLISHERS: dict[str, AppPublisher] = {
    "youtube": YouTubePublisher(),
    "tiktok": TikTokPublisher(),
    "instagram": InstagramPublisher(),
    "x": XPublisher(),
}


def publisher_for(platform: str) -> AppPublisher:
    return PUBLISHERS[platform]


__all__ = ["PUBLISHERS", "AppPublisher", "publisher_for"]
