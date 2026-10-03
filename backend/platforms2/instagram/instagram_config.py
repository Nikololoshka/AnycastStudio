from dataclasses import dataclass, field


@dataclass(frozen=True)
class InstagramConfig:
    client_id: str
    client_secret: str = field(repr=False)
    redirect_uri: str
    scopes: tuple[str, ...] = (
        "instagram_basic",
        "instagram_content_publish",
        "pages_show_list",
        "pages_read_engagement",
    )
    chunk_bytes: int = 8 * 1024**2
    retries: int = 5
