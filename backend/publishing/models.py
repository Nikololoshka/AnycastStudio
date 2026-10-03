from django.conf import settings
from django.db import models
from django.utils import timezone

from platforms.core.publications import TargetStatus


class Publication(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="publications"
    )
    asset = models.ForeignKey(
        "media.MediaAsset", on_delete=models.PROTECT, related_name="publications"
    )

    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    hashtags = models.JSONField(default=list, blank=True)

    publish_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.title or f"publication {self.pk}"


class PublicationTarget(models.Model):
    Status = models.TextChoices("Status", [(status.name, status.value) for status in TargetStatus])

    RUNNING = TargetStatus.running()
    ACTIVE = TargetStatus.active()

    publication = models.ForeignKey(
        Publication, on_delete=models.CASCADE, related_name="targets"
    )
    platform = models.CharField(max_length=32)
    social_account = models.ForeignKey(
        "social.SocialAccount", on_delete=models.PROTECT, related_name="targets"
    )

    settings = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    progress = models.PositiveSmallIntegerField(default=0)
    uploaded_bytes = models.BigIntegerField(default=0)
    total_bytes = models.BigIntegerField(default=0)

    uploaded_media_id = models.CharField(max_length=128, blank=True)
    confirmation_state = models.JSONField(null=True, blank=True)

    published_url = models.URLField(blank=True, max_length=500)
    error = models.JSONField(null=True, blank=True)

    attempt_count = models.PositiveSmallIntegerField(default=0)
    cancel_requested = models.BooleanField(default=False)

    started_at = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["publication", "platform"], name="unique_target_per_platform"
            )
        ]

    def __str__(self) -> str:
        return f"{self.platform}:{self.status}"

    @property
    def is_active(self) -> bool:
        return self.status in self.ACTIVE
