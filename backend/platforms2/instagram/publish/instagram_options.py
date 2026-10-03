from collections.abc import Mapping
from dataclasses import dataclass
from typing import Self


@dataclass(frozen=True)
class InstagramOptions:
    share_to_feed: bool = True
    cover_frame_seconds: float = 0

    @classmethod
    def of(cls, raw: Mapping) -> Self:
        share_to_feed = raw.get("shareToFeed")
        return cls(
            share_to_feed=share_to_feed if isinstance(share_to_feed, bool) else True,
            cover_frame_seconds=cls._seconds(raw.get("coverFrameSeconds")),
        )

    @property
    def thumb_offset_ms(self) -> int:
        return round(self.cover_frame_seconds * 1000)

    @staticmethod
    def _seconds(value) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return 0
        return float(value) if value > 0 else 0
