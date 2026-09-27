from types import ModuleType

from . import instagram, tiktok, x, youtube
from .outcome import Published

PUBLISHERS: dict[str, ModuleType] = {"youtube": youtube, "tiktok": tiktok, "instagram": instagram, "x": x}


def publisher_for(platform: str) -> ModuleType:
    return PUBLISHERS[platform]


__all__ = ["PUBLISHERS", "Published", "publisher_for"]
