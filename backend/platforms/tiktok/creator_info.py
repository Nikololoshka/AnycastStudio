from pydantic import Field

from ..core.http import PlatformModel
from ..upload import fresh_token_on_rejection
from .client import API_ROOT, call

CREATOR_INFO_ENDPOINT = f"{API_ROOT}/post/publish/creator_info/query/"


class CreatorInfo(PlatformModel):
    username: str = Field("", alias="creator_username")
    nickname: str = Field("", alias="creator_nickname")
    avatar_url: str = Field("", alias="creator_avatar_url")
    privacy_level_options: tuple[str, ...] = ()
    comment_disabled: bool = False
    duet_disabled: bool = False
    stitch_disabled: bool = False
    max_video_post_duration_sec: int | None = None

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


def query(access_token: str) -> CreatorInfo:
    return fresh_token_on_rejection(lambda: call("POST", CREATOR_INFO_ENDPOINT, access_token, CreatorInfo))
