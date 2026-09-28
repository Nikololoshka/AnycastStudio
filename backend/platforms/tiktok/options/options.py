from collections.abc import Mapping
from dataclasses import dataclass
from typing import Self

PRIVACY_VALUES = ("PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "SELF_ONLY")
PRIVATE = "SELF_ONLY"


@dataclass(frozen=True)
class TikTokOptions:
    privacy_level: str | None = None
    disable_comment: bool = False
    disable_duet: bool = False
    disable_stitch: bool = False
    disclose_content: bool = False
    brand_organic: bool = False
    brand_content: bool = False
    is_aigc: bool = False
    cover_frame_seconds: float = 0

    @classmethod
    def of(cls, raw) -> Self:
        raw = raw if isinstance(raw, Mapping) else {}
        privacy = raw.get("privacyLevel")
        return cls(
            privacy_level=privacy if privacy in PRIVACY_VALUES else None,
            disable_comment=cls._flag(raw, "disableComment"),
            disable_duet=cls._flag(raw, "disableDuet"),
            disable_stitch=cls._flag(raw, "disableStitch"),
            disclose_content=cls._flag(raw, "discloseContent"),
            brand_organic=cls._flag(raw, "brandOrganic"),
            brand_content=cls._flag(raw, "brandContent"),
            is_aigc=cls._flag(raw, "isAigc"),
            cover_frame_seconds=cls._seconds(raw.get("coverFrameSeconds")),
        )

    def as_json(self) -> dict:
        return {
            "privacyLevel": self.privacy_level,
            "disableComment": self.disable_comment,
            "disableDuet": self.disable_duet,
            "disableStitch": self.disable_stitch,
            "discloseContent": self.disclose_content,
            "brandOrganic": self.brand_organic,
            "brandContent": self.brand_content,
            "isAigc": self.is_aigc,
            "coverFrameSeconds": self.cover_frame_seconds,
        }

    @property
    def is_private(self) -> bool:
        return self.privacy_level == PRIVATE

    @property
    def brand_organic_toggle(self) -> bool:
        return self.disclose_content and self.brand_organic

    @property
    def brand_content_toggle(self) -> bool:
        return self.disclose_content and self.brand_content

    @property
    def cover_timestamp_ms(self) -> int | None:
        return round(self.cover_frame_seconds * 1000) if self.cover_frame_seconds > 0 else None

    @staticmethod
    def _flag(raw: Mapping, key: str) -> bool:
        return bool(raw.get(key) or False)

    @staticmethod
    def _seconds(value) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return 0
        return float(value) if value > 0 else 0
