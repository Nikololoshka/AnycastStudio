from .instagram import InstagramPublisher
from .publisher import AppPublisher
from .x import XPublisher

PUBLISHERS: dict[str, AppPublisher] = {
    "instagram": InstagramPublisher(),
    "x": XPublisher(),
}


def publisher_for(platform: str) -> AppPublisher:
    return PUBLISHERS[platform]


__all__ = ["PUBLISHERS", "AppPublisher", "publisher_for"]
