"""Encryption at rest for platform tokens.

Values are encrypted with Fernet before they reach the database and decrypted
on the way out, so a copy of the database file is not a copy of the tokens.

TOKEN_ENCRYPTION_KEYS is ordered newest first. MultiFernet encrypts with the
first key and decrypts with any of them, so a key is rotated by prepending the
new one and re-saving the rows; the old key is removed once nothing needs it.
The keys are deliberately not derived from DJANGO_SECRET_KEY: they rotate on a
different schedule and losing them costs every user every connected account.
"""

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


def _key_material(entry: str) -> str:
    """Accept either "v1:<key>" or a bare key."""
    _, _, key = entry.rpartition(":")
    return key or entry


@lru_cache(maxsize=1)
def _cipher() -> MultiFernet:
    keys = getattr(settings, "TOKEN_ENCRYPTION_KEYS", [])
    if not keys:
        raise ImproperlyConfigured("TOKEN_ENCRYPTION_KEYS must be set to store platform tokens")
    return MultiFernet([Fernet(_key_material(entry)) for entry in keys])


def current_key_version() -> str:
    version, separator, _ = settings.TOKEN_ENCRYPTION_KEYS[0].partition(":")
    return version if separator else ""


def reset_cipher_cache() -> None:
    """Call after changing TOKEN_ENCRYPTION_KEYS at runtime, which only tests do."""
    _cipher.cache_clear()


class EncryptedTextField(models.TextField):
    """A TextField whose value is stored as Fernet ciphertext.

    The column holds text, so it cannot be searched, indexed or compared in SQL.
    That is intended: these values are read one row at a time by the worker.
    """

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
            # The row was written with a key that is no longer configured. Report it as
            # missing rather than crashing: the account simply needs reconnecting.
            return ""
