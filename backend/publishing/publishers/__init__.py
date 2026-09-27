from .instagram import InstagramPublisher
from .outcome import Published
from .publisher import Publisher
from .tiktok import TikTokPublisher
from .x import XPublisher
from .youtube import YouTubePublisher

PUBLISHERS: dict[str, Publisher] = {
    "youtube": YouTubePublisher(),
    "tiktok": TikTokPublisher(),
    "instagram": InstagramPublisher(),
    "x": XPublisher(),
}


def publisher_for(platform: str) -> Publisher:
    return PUBLISHERS[platform]


__all__ = ["PUBLISHERS", "Published", "Publisher", "publisher_for"]
