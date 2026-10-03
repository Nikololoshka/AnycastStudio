from dataclasses import dataclass
from typing import Self

from platforms.core import PublishDraft

from .instagram_options import InstagramOptions


@dataclass(frozen=True)
class ReelInfo:
    caption: str
    share_to_feed: bool
    thumb_offset_ms: int

    @classmethod
    def of(cls, draft: PublishDraft) -> Self:
        options = InstagramOptions.of(draft.settings)
        return cls(draft.caption(), options.share_to_feed, options.thumb_offset_ms)

    def as_form(self) -> dict:
        return {
            "media_type": "REELS",
            "upload_type": "resumable",
            "caption": self.caption,
            "share_to_feed": "true" if self.share_to_feed else "false",
            "thumb_offset": str(self.thumb_offset_ms),
        }
