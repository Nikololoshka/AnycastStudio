from pydantic import Field

from ...core import InstagramAnswer


class UserToken(InstagramAnswer):
    access_token: str = Field(min_length=1)
