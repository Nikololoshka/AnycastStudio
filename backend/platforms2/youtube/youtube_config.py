from dataclasses import dataclass, field


@dataclass(frozen=True)
class YouTubeConfig:
    client_id: str
    client_secret: str = field(repr=False)
    redirect_uri: str
    scopes: tuple[str, ...] = (
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube",
    )
