from pydantic import Field

from ...core import XAnswer


class Identified(XAnswer):
    id: str = Field(min_length=1)


class Created(XAnswer):
    data: Identified
