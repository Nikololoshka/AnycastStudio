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
    chunk_bytes: int = 8 * 1024**2
    retries: int = 5
    http_timeout: float = 60

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)
