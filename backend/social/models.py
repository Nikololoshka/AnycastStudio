from django.conf import settings
from django.db import models
from django.utils import timezone

from common.encryption import EncryptedTextField
from services.core.accounts import AccountStatus, OAuthSessionStatus


class SocialAccount(models.Model):
    Status = models.TextChoices("Status", [(status.name, status.value) for status in AccountStatus])

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="social_accounts"
    )
    platform = models.CharField(max_length=32)
    external_id = models.CharField(max_length=128)

    display_name = models.CharField(max_length=200, blank=True)
    avatar_url = models.URLField(blank=True, max_length=500)

    access_token = EncryptedTextField(blank=True)
    refresh_token = EncryptedTextField(blank=True)
    key_version = models.CharField(max_length=8, blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    scopes = models.JSONField(default=list, blank=True)

    extra = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    last_refresh_at = models.DateTimeField(null=True, blank=True)
    refresh_lease_until = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)
    connected_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "platform", "external_id"], name="unique_account_per_user"
            )
        ]

    def __str__(self) -> str:
        return f"{self.platform}:{self.display_name or self.external_id}"


class OAuthSession(models.Model):
    Status = models.TextChoices("Status", [(status.name, status.value) for status in OAuthSessionStatus])

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="oauth_sessions"
    )
    platform = models.CharField(max_length=32)
    state = models.CharField(max_length=64, unique=True)
    code_verifier = EncryptedTextField(blank=True)

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    def __str__(self) -> str:
        return f"{self.platform}:{self.status}:{self.pk}"
