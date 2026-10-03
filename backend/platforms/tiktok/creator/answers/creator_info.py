from pydantic import Field

from ...core import TikTokAnswer


class Creator(TikTokAnswer):
    username: str = Field("", alias="creator_username")
    nickname: str = Field("", alias="creator_nickname")
    avatar_url: str = Field("", alias="creator_avatar_url")
    privacy_level_options: tuple[str, ...] = ()
    comment_disabled: bool = False
    duet_disabled: bool = False
    stitch_disabled: bool = False
    max_video_post_duration_sec: int | None = None

    def refusals(self, privacy_level: str | None, duration_seconds: float | None) -> list[str]:
        refusals: list[str] = []
        if privacy_level not in self.privacy_level_options:
            refusals.append("privacyNotOffered")
        limit = self.max_video_post_duration_sec
        if limit and duration_seconds and duration_seconds > limit:
            refusals.append("videoTooLong")
        return refusals

    def as_json(self) -> dict:
        return {
            "username": self.username,
            "nickname": self.nickname,
            "avatarUrl": self.avatar_url,
            "privacyLevelOptions": list(self.privacy_level_options),
            "commentDisabled": self.comment_disabled,
            "duetDisabled": self.duet_disabled,
            "stitchDisabled": self.stitch_disabled,
            "maxVideoPostDurationSec": self.max_video_post_duration_sec,
        }


class CreatorInfo(TikTokAnswer):
    data: Creator
