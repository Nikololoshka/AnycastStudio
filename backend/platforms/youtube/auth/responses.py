from pydantic import Field

from ...core.http import PlatformModel


class Thumbnail(PlatformModel):
    url: str = ""


class Thumbnails(PlatformModel):
    default: Thumbnail = Thumbnail()


class Snippet(PlatformModel):
    title: str = ""
    custom_url: str = Field("", alias="customUrl")
    thumbnails: Thumbnails = Thumbnails()


class Channel(PlatformModel):
    id: str = ""
    snippet: Snippet = Snippet()


class ChannelList(PlatformModel):
    items: list[Channel] = []

