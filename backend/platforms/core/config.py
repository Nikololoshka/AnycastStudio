from collections.abc import Mapping
from dataclasses import dataclass, field

CALLBACK_PATH = "/api/social/{platform}/callback"


@dataclass(frozen=True)
class HttpConfig:
    timeout: float = 10
    attempts: int = 5


@dataclass(frozen=True)
class UploadConfig:
    chunk_bytes: int = 8 * 1024**2
    stall_limit: int = 5


@dataclass(frozen=True)
class OAuthCredentials:
    client_id_name: str
    client_secret_name: str
    client_id: str = ""
    client_secret: str = field(default="", repr=False)


@dataclass(frozen=True)
class PlatformConfig:
    http: HttpConfig = HttpConfig()
    upload: UploadConfig = UploadConfig()
    redirect_origin: str = ""
    credentials: Mapping[str, OAuthCredentials] = field(default_factory=dict)

    def callback_url(self, platform: str) -> str:
        return f"{self.redirect_origin}{CALLBACK_PATH.format(platform=platform)}"

    def credentials_of(self, platform: str) -> OAuthCredentials:
        return self.credentials[platform]
