from functools import lru_cache

from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _key_without_version(entry: str) -> str:
    _, _, key = entry.rpartition(":")
    return key or entry


@lru_cache(maxsize=1)
def cipher() -> MultiFernet:
    keys = getattr(settings, "TOKEN_ENCRYPTION_KEYS", [])
    if not keys:
        raise ImproperlyConfigured("TOKEN_ENCRYPTION_KEYS must be set to store platform tokens")
    return MultiFernet([Fernet(_key_without_version(entry)) for entry in keys])


def current_key_version() -> str:
    version, separator, _ = settings.TOKEN_ENCRYPTION_KEYS[0].partition(":")
    return version if separator else ""


def reset_cipher_cache() -> None:
    cipher.cache_clear()
