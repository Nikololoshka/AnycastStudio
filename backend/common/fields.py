import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models

logger = logging.getLogger(__name__)


def _key_without_version(entry: str) -> str:
    _, _, key = entry.rpartition(":")
    return key or entry


@lru_cache(maxsize=1)
def _cipher() -> MultiFernet:
    keys = getattr(settings, "TOKEN_ENCRYPTION_KEYS", [])
    if not keys:
        raise ImproperlyConfigured("TOKEN_ENCRYPTION_KEYS must be set to store platform tokens")
    return MultiFernet([Fernet(_key_without_version(entry)) for entry in keys])


def current_key_version() -> str:
    version, separator, _ = settings.TOKEN_ENCRYPTION_KEYS[0].partition(":")
    return version if separator else ""


def reset_cipher_cache() -> None:
    _cipher.cache_clear()


class EncryptedTextField(models.TextField):
    def get_prep_value(self, value):
        if value is None or value == "":
            return value
        return _cipher().encrypt(str(value).encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        try:
            return _cipher().decrypt(value.encode()).decode()
        except InvalidToken:
            logger.warning(
                "%s.%s was written with a key that is no longer configured; the account must reconnect",
                self.model.__name__,
                self.name,
            )
            return ""
