from pydantic import Field

from ..x_answer import XAnswer


class Identified(XAnswer):
    id: str = Field(min_length=1)


class Created(XAnswer):
    data: Identified
