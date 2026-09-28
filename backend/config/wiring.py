from functools import cache, cached_property

from django.conf import settings
from django.core.signals import setting_changed

from platforms.core.config import HttpConfig, OAuthCredentials, PlatformConfig, UploadConfig
from platforms.core.ports import Clock, SystemClock

CREDENTIAL_SETTINGS = {
    "youtube": ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET"),
    "tiktok": ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET"),
    "instagram": ("INSTAGRAM_CLIENT_ID", "INSTAGRAM_CLIENT_SECRET"),
    "x": ("X_CLIENT_ID", "X_CLIENT_SECRET"),
}


def _credentials(id_name: str, secret_name: str) -> OAuthCredentials:
    return OAuthCredentials(
        client_id_name=id_name,
        client_secret_name=secret_name,
        client_id=getattr(settings, id_name, ""),
        client_secret=getattr(settings, secret_name, ""),
    )


class Container:
    @cached_property
    def config(self) -> PlatformConfig:
        return PlatformConfig(
            http=HttpConfig(timeout=settings.HTTP_TIMEOUT, attempts=settings.UPLOAD_RETRY_ATTEMPTS),
            upload=UploadConfig(chunk_bytes=settings.PLATFORM_CHUNK_BYTES, stall_limit=settings.UPLOAD_RETRY_ATTEMPTS),
            redirect_origin=settings.PUBLIC_REDIRECT_ORIGIN,
            credentials={name: _credentials(*names) for name, names in CREDENTIAL_SETTINGS.items()},
        )

    @cached_property
    def clock(self) -> Clock:
        return SystemClock()


@cache
def container() -> Container:
    return Container()


def _forget_container(**_) -> None:
    container.cache_clear()


setting_changed.connect(_forget_container, dispatch_uid="config.wiring.forget_container")
