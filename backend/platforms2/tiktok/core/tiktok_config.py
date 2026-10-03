from dataclasses import dataclass, field


@dataclass(frozen=True)
class TikTokConfig:
    client_key: str
    client_secret: str = field(repr=False)
    redirect_uri: str
    scopes: tuple[str, ...] = ("user.info.basic", "video.publish")
    chunk_bytes: int = 8 * 1024**2
    retries: int = 5
