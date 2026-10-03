from pydantic import Field

from ..google_answer import GoogleAnswer


class UploadedVideo(GoogleAnswer):
    id: str = Field(min_length=1)
