from dataclasses import dataclass, field


@dataclass(frozen=True)
class XConfig:
    client_id: str
    client_secret: str = field(repr=False)
    redirect_uri: str
    scopes: tuple[str, ...] = ("tweet.read", "tweet.write", "users.read", "media.write", "offline.access")
