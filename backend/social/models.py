"""Connected platform accounts, and the short-lived state of connecting one."""

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from common.encryption import EncryptedTextField

# A token is refreshed this long before it expires, so a request that starts now
# does not finish with a token that expired mid-upload.
REFRESH_MARGIN = timedelta(minutes=5)


class SocialAccount(models.Model):
    """One platform account, owned by one person.

    The tokens are the only thing of value here, so they are encrypted at rest
    and never leave the server: no API response and no log line contains them.
    """

    class Status(models.TextChoices):
        ACTIVE = "active"
        NEEDS_REAUTH = "needs_reauth"
        REVOKED = "revoked"

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
    last_error = models.CharField(max_length=500, blank=True)
    connected_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "platform", "external_id"], name="unique_account_per_user"
            )
        ]

    def __str__(self) -> str:
        # Never interpolate a token field here: this string reaches logs and the admin.
        return f"{self.platform}:{self.display_name or self.external_id}"

    @property
    def needs_refresh(self) -> bool:
        if not self.token_expires_at:
            return False
        return timezone.now() >= self.token_expires_at - REFRESH_MARGIN


class OAuthSession(models.Model):
    """One in-flight authorisation, from the redirect out to the redirect back.

    `state` ties the callback to the person who started it. Without that check a
    stranger could graft their own platform account onto someone else's tenant.
    """

    class Status(models.TextChoices):
        PENDING = "pending"
        PROCESSING = "processing"
        DONE = "done"
        ERROR = "error"

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

    @staticmethod
    def expiry_cutoff():
        return timezone.now() - timedelta(seconds=settings.OAUTH_SESSION_TTL)

    @property
    def is_expired(self) -> bool:
        return self.created_at < self.expiry_cutoff()
