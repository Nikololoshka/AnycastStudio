from pydantic import Field

from ..instagram_answer import InstagramAnswer


class UserToken(InstagramAnswer):
    access_token: str = Field(min_length=1)
