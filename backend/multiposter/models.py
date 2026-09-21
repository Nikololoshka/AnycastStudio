import hashlib
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AuthSession(models.Model):
    
    class Status(models.TextChoices):
        PENDING = "pending"
        PROCESSING = "processing"
        DONE = "done"
        ERROR = "error"

    provider = models.CharField(max_length=32)
    state = models.CharField(max_length=64, unique=True)
    poll_token_hash = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    result = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    def __str__(self):
        return f"{self.provider}:{self.status}:{self.pk}"

    @staticmethod
    def expiry_cutoff():
        return timezone.now() - timedelta(seconds=settings.AUTH_SESSION_TTL)

    @property
    def is_expired(self) -> bool:
        return self.created_at < self.expiry_cutoff()
