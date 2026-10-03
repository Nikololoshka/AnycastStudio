from pydantic import Field

from ...core import TikTokAnswer
from ..tiktok_options import TikTokOptions


class Creator(TikTokAnswer):
    username: str = Field("", alias="creator_username")
    privacy_level_options: tuple[str, ...] = ()
    comment_disabled: bool = False
    duet_disabled: bool = False
    stitch_disabled: bool = False
    max_video_post_duration_sec: int | None = None

    def refusals(self, options: TikTokOptions, duration_seconds: float | None) -> list[str]:
        refusals: list[str] = []
        if options.privacy_level not in self.privacy_level_options:
            refusals.append("privacyNotOffered")
        limit = self.max_video_post_duration_sec
        if limit and duration_seconds and duration_seconds > limit:
            refusals.append("videoTooLong")
        return refusals


class CreatorInfo(TikTokAnswer):
    data: Creator
