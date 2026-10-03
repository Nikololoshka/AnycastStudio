from dataclasses import dataclass, field


@dataclass(frozen=True)
class XConfig:
    client_id: str
    client_secret: str = field(repr=False)
    redirect_uri: str
    scopes: tuple[str, ...] = ("tweet.read", "tweet.write", "users.read", "media.write", "offline.access")
    segment_bytes: int = 4 * 1024**2
    retries: int = 5

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)
