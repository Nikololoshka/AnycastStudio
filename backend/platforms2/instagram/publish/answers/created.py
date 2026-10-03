from pydantic import Field

from ...core import InstagramAnswer


class Created(InstagramAnswer):
    id: str = Field(min_length=1)
