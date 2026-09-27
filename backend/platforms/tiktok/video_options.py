from dataclasses import dataclass

PRIVACY_VALUES = ("PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "SELF_ONLY")
PRIVATE = "SELF_ONLY"

MAX_CAPTION_LENGTH = 2200


@dataclass(frozen=True)
class VideoOptions:
    privacy_level: str | None = None
    disable_comment: bool = False
    disable_duet: bool = False
    disable_stitch: bool = False
    disclose_content: bool = False
    brand_organic: bool = False
    brand_content: bool = False
    is_aigc: bool = False
    cover_frame_seconds: float = 0

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
    def brand_organic_toggle(self) -> bool:
        return self.disclose_content and self.brand_organic

    @property
    def brand_content_toggle(self) -> bool:
        return self.disclose_content and self.brand_content

    @property
    def cover_timestamp_ms(self) -> int | None:
        return round(self.cover_frame_seconds * 1000) if self.cover_frame_seconds > 0 else None


def _flag(raw: dict, key: str) -> bool:
    return bool(raw.get(key) or False)


def _seconds(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return float(value) if value > 0 else 0


def video_options_of(raw) -> VideoOptions:
    raw = raw if isinstance(raw, dict) else {}
    privacy = raw.get("privacyLevel")
    return VideoOptions(
        privacy_level=privacy if privacy in PRIVACY_VALUES else None,
        disable_comment=_flag(raw, "disableComment"),
        disable_duet=_flag(raw, "disableDuet"),
        disable_stitch=_flag(raw, "disableStitch"),
        disclose_content=_flag(raw, "discloseContent"),
        brand_organic=_flag(raw, "brandOrganic"),
        brand_content=_flag(raw, "brandContent"),
        is_aigc=_flag(raw, "isAigc"),
        cover_frame_seconds=_seconds(raw.get("coverFrameSeconds")),
    )


def caption_of(title: str, description: str, hashtags: list[str]) -> str:
    tags = " ".join(f"#{tag}" for tag in hashtags)
    return "\n\n".join(part for part in (title.strip(), description.strip(), tags) if part)


def utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2
