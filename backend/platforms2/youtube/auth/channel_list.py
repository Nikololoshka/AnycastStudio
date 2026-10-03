from ..google_answer import GoogleAnswer


class Thumbnail(GoogleAnswer):
    url: str = ""


class Thumbnails(GoogleAnswer):
    default: Thumbnail = Thumbnail()


class Snippet(GoogleAnswer):
    title: str = ""
    thumbnails: Thumbnails = Thumbnails()


class Channel(GoogleAnswer):
    id: str
    snippet: Snippet = Snippet()


class ChannelList(GoogleAnswer):
    items: list[Channel] = []
