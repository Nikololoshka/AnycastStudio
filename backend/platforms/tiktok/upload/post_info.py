from dataclasses import dataclass
from typing import Self

from ...core.publishing import PublicationDraft
from ..account.creator_info import CreatorInfo
from ..options import TikTokOptions


@dataclass(frozen=True)
class PostInfo:
    title: str
    privacy_level: str
    disable_comment: bool
    disable_duet: bool
    disable_stitch: bool
    brand_content_toggle: bool
    brand_organic_toggle: bool
    is_aigc: bool
    video_cover_timestamp_ms: int | None = None

    @classmethod
    def of(cls, draft: PublicationDraft, options: TikTokOptions, creator: CreatorInfo) -> Self:
        return cls(
            title=draft.caption(),
            privacy_level=options.privacy_level or "",
            disable_comment=options.disable_comment or creator.comment_disabled,
            disable_duet=options.disable_duet or creator.duet_disabled,
            disable_stitch=options.disable_stitch or creator.stitch_disabled,
            brand_content_toggle=options.brand_content_toggle,
            brand_organic_toggle=options.brand_organic_toggle,
            is_aigc=options.is_aigc,
            video_cover_timestamp_ms=options.cover_timestamp_ms,
        )

    def as_body(self) -> dict:
        body = {
            "title": self.title,
            "privacy_level": self.privacy_level,
            "disable_comment": self.disable_comment,
            "disable_duet": self.disable_duet,
            "disable_stitch": self.disable_stitch,
            "brand_content_toggle": self.brand_content_toggle,
            "brand_organic_toggle": self.brand_organic_toggle,
            "is_aigc": self.is_aigc,
        }
        if self.video_cover_timestamp_ms is not None:
            body["video_cover_timestamp_ms"] = self.video_cover_timestamp_ms
        return body
