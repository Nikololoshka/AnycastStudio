from dataclasses import dataclass, field


@dataclass(frozen=True)
class TikTokConfig:
    client_key: str
    client_secret: str = field(repr=False)
    redirect_uri: str
    scopes: tuple[str, ...] = ("user.info.basic", "video.publish")
