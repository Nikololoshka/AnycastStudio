from pydantic import Field

from ...core import TikTokAnswer


class User(TikTokAnswer):
    open_id: str = Field(min_length=1)
    display_name: str = ""
    avatar_url: str = ""


class UserData(TikTokAnswer):
    user: User


class UserInfo(TikTokAnswer):
    data: UserData
