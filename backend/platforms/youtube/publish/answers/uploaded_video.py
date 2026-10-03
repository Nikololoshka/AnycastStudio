from pydantic import Field

from ...core import GoogleAnswer


class UploadedVideo(GoogleAnswer):
    id: str = Field(min_length=1)
