from dataclasses import dataclass

from ..http import AUTHENTICATION, PlatformFailure
from .api import API_ROOT, call
from .errors import NeedsFreshToken

CREATOR_INFO_ENDPOINT = f"{API_ROOT}/post/publish/creator_info/query/"


@dataclass(frozen=True)
class CreatorInfo:
    username: str
    nickname: str
    avatar_url: str
    privacy_level_options: tuple[str, ...]
    comment_disabled: bool
    duet_disabled: bool
    stitch_disabled: bool
    max_video_post_duration_sec: int | None

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
    try:
        data = call("POST", CREATOR_INFO_ENDPOINT, access_token)
    except PlatformFailure as failure:
        if failure.type == AUTHENTICATION:
            raise NeedsFreshToken(None, failure.message) from None
        raise

    duration = data.get("max_video_post_duration_sec")
    return CreatorInfo(
        username=str(data.get("creator_username") or ""),
        nickname=str(data.get("creator_nickname") or ""),
        avatar_url=str(data.get("creator_avatar_url") or ""),
        privacy_level_options=tuple(str(option) for option in data.get("privacy_level_options") or ()),
        comment_disabled=bool(data.get("comment_disabled")),
        duet_disabled=bool(data.get("duet_disabled")),
        stitch_disabled=bool(data.get("stitch_disabled")),
        max_video_post_duration_sec=int(duration) if isinstance(duration, (int, float)) else None,
    )
