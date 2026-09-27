import re
from dataclasses import dataclass

MAX_CAPTION_LENGTH = 2200
MAX_HASHTAGS = 30

HASHTAG = re.compile(r"(?<![\w#])#\w+")


@dataclass(frozen=True)
class VideoOptions:
    share_to_feed: bool = True
    cover_frame_seconds: float = 0

    def as_json(self) -> dict:
        return {"shareToFeed": self.share_to_feed, "coverFrameSeconds": self.cover_frame_seconds}

    @property
    def thumb_offset_ms(self) -> int:
        return round(self.cover_frame_seconds * 1000)


def _seconds(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return float(value) if value > 0 else 0


def video_options_of(raw) -> VideoOptions:
    raw = raw if isinstance(raw, dict) else {}
    share_to_feed = raw.get("shareToFeed")
    return VideoOptions(
        share_to_feed=share_to_feed if isinstance(share_to_feed, bool) else True,
        cover_frame_seconds=_seconds(raw.get("coverFrameSeconds")),
    )


def caption_of(title: str, description: str, hashtags: list[str]) -> str:
    tags = " ".join(f"#{tag}" for tag in hashtags)
    return "\n\n".join(part for part in (title.strip(), description.strip(), tags) if part)


def hashtag_count(caption: str) -> int:
    return len(HASHTAG.findall(caption))
