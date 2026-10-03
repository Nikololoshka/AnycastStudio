from pydantic import Field

from ..instagram_answer import InstagramAnswer


class Created(InstagramAnswer):
    id: str = Field(min_length=1)
