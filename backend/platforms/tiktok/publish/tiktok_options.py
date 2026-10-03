from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, Self


@dataclass(frozen=True)
class TikTokOptions:
    PRIVACY_VALUES: ClassVar = ("PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "SELF_ONLY")
    PRIVATE: ClassVar = "SELF_ONLY"

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
    def of(cls, raw: Mapping) -> Self:
        privacy = raw.get("privacyLevel")
        return cls(
            privacy_level=privacy if privacy in cls.PRIVACY_VALUES else None,
            disable_comment=bool(raw.get("disableComment")),
            disable_duet=bool(raw.get("disableDuet")),
            disable_stitch=bool(raw.get("disableStitch")),
            disclose_content=bool(raw.get("discloseContent")),
            brand_organic=bool(raw.get("brandOrganic")),
            brand_content=bool(raw.get("brandContent")),
            is_aigc=bool(raw.get("isAigc")),
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
        return self.privacy_level == self.PRIVATE

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
    def _seconds(value) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return 0
        return float(value) if value > 0 else 0
