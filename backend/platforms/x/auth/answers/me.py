from pydantic import Field

from ...core import XAnswer


class User(XAnswer):
    id: str = Field(min_length=1)
    username: str = ""
    name: str = ""
    profile_image_url: str = ""


class Me(XAnswer):
    data: User
