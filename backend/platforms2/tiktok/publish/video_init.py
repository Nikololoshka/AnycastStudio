from pydantic import Field

from ..tiktok_answer import TikTokAnswer


class Upload(TikTokAnswer):
    publish_id: str = Field(min_length=1)
    upload_url: str = Field(min_length=1)


class VideoInit(TikTokAnswer):
    data: Upload
