import logging

from cryptography.fernet import InvalidToken
from django.db import models

from .keys import cipher

logger = logging.getLogger(__name__)


class EncryptedTextField(models.TextField):
    def get_prep_value(self, value):
        if value is None or value == "":
            return value
        return cipher().encrypt(str(value).encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        try:
            return cipher().decrypt(value.encode()).decode()
        except InvalidToken:
            logger.warning(
                "%s.%s was written with a key that is no longer configured; the account must reconnect",
                self.model.__name__,
                self.name,
            )
            return ""
