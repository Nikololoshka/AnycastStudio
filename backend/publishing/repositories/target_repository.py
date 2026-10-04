from collections.abc import Iterable
from datetime import datetime

from asgiref.sync import sync_to_async
from django.db.models import F, Q, Value
from django.db.models.functions import Coalesce

from media import storage
from platforms.core import PlatformType, PublishDraft, PublishJob, PublishMedia
from services.core.domain import NotFound
from services.core.ports import TargetRepository
from services.core.publications import TargetStatus

from ..models import PublicationTarget


class DjangoTargetRepository(TargetRepository):
    @sync_to_async
    def get_publish_job(self, target_id: int) -> PublishJob:
        target = (
            PublicationTarget.objects.select_related(
                "publication", "publication__asset", "social_account"
            ).get(pk=target_id)
        )
        publication = target.publication
        asset = publication.asset
        return PublishJob(
            target_id=target.pk,
            platform=PlatformType(target.platform),
            account_id=target.social_account_id,
            external_id=target.social_account.external_id,
            draft=PublishDraft(
                title=publication.title,
                description=publication.description,
                hashtags=tuple(publication.hashtags),
                settings=target.settings or {},
            ),
            media=PublishMedia(
                path=storage.absolute(asset.storage_path),
                size_bytes=asset.size_bytes,
                mime_type=asset.mime_type,
                duration_seconds=asset.duration_seconds,
            ),
            publish_at=publication.publish_at,
            media_id=target.uploaded_media_id,
            confirmation_state=target.confirmation_state or {},
        )

    @sync_to_async
    def claim_queued_target(self, target_id: int, now: datetime) -> bool:
        return bool(
            PublicationTarget.objects.filter(pk=target_id, status=TargetStatus.QUEUED).update(
                status=TargetStatus.VALIDATING,
                started_at=Coalesce("started_at", Value(now)),
                last_activity_at=now,
            )
        )

    @sync_to_async
    def start_target_attempt(self, target_id: int, now: datetime) -> None:
        PublicationTarget.objects.filter(pk=target_id).update(
            attempt_count=F("attempt_count") + 1, error=None, last_activity_at=now
        )

    @sync_to_async
    def update_target(self, target_id: int, **fields) -> None:
        PublicationTarget.objects.filter(pk=target_id).update(**fields)

    @sync_to_async
    def is_cancel_requested(self, target_id: int) -> bool:
        return PublicationTarget.objects.filter(pk=target_id, cancel_requested=True).exists()

    @sync_to_async
    def claim_confirmation_poll(self, target_id: int, now: datetime) -> bool:
        waiting = PublicationTarget.objects.filter(pk=target_id, status=TargetStatus.PROCESSING)
        row = waiting.values("last_activity_at").first()
        if row is None:
            return False
        return bool(waiting.filter(last_activity_at=row["last_activity_at"]).update(last_activity_at=now))

    @sync_to_async
    def claim_due_targets(
            self, platforms: Iterable[PlatformType], now: datetime, dispatched_before: datetime
    ) -> list[int]:
        not_recently_dispatched = Q(last_activity_at__isnull=True) | Q(last_activity_at__lt=dispatched_before)
        due = PublicationTarget.objects.filter(
            not_recently_dispatched,
            status=TargetStatus.QUEUED,
            platform__in=list(platforms),
            publication__publish_at__lte=now,
        ).values_list("pk", flat=True)
        return [
            pk
            for pk in list(due)
            if PublicationTarget.objects.filter(not_recently_dispatched, pk=pk, status=TargetStatus.QUEUED).update(
                last_activity_at=now
            )
        ]

    @sync_to_async
    def claim_stalled_confirmations(self, now: datetime, stalled_before: datetime) -> list[int]:
        stalled = Q(status=TargetStatus.PROCESSING, last_activity_at__lt=stalled_before)
        candidates = PublicationTarget.objects.filter(stalled).values_list("pk", flat=True)
        return [
            pk for pk in list(candidates) if
            PublicationTarget.objects.filter(stalled, pk=pk).update(last_activity_at=now)
        ]

    @sync_to_async
    def fail_abandoned_targets(self, now: datetime, abandoned_before: datetime, failure: dict) -> list[int]:
        abandoned = Q(status__in=TargetStatus.worked_on(), last_activity_at__lt=abandoned_before)
        candidates = PublicationTarget.objects.filter(abandoned).values_list("pk", flat=True)
        return [
            pk
            for pk in list(candidates)
            if PublicationTarget.objects.filter(abandoned, pk=pk).update(
                status=TargetStatus.FAILED, error=failure, finished_at=now, last_activity_at=now
            )
        ]

    @sync_to_async
    def ensure_target_owned(self, owner_id: int, target_id: int) -> None:
        if not PublicationTarget.objects.filter(publication__user_id=owner_id, pk=target_id).exists():
            raise NotFound()

    @sync_to_async
    def get_target_status(self, target_id: int) -> TargetStatus:
        return TargetStatus(PublicationTarget.objects.values_list("status", flat=True).get(pk=target_id))

    @sync_to_async
    def request_target_cancel(self, target_id: int, now: datetime) -> None:
        PublicationTarget.objects.filter(pk=target_id).update(cancel_requested=True)
        PublicationTarget.objects.filter(pk=target_id, status=TargetStatus.QUEUED).update(
            status=TargetStatus.CANCELLED, finished_at=now
        )

    @sync_to_async
    def reset_target_for_retry(self, target_id: int) -> None:
        PublicationTarget.objects.filter(pk=target_id).update(
            status=TargetStatus.QUEUED,
            cancel_requested=False,
            error=None,
            finished_at=None,
            last_activity_at=None,
            uploaded_media_id="",
            confirmation_state=None,
        )
