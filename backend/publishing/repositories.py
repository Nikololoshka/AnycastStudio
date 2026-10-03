from collections.abc import Iterable
from datetime import datetime

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Q, Value
from django.db.models.functions import Coalesce

from media import storage
from media.models import MediaAsset
from platforms2.core import PlatformType, PublishDraft, PublishJob, PublishMedia
from platforms2.core.domain import NotFound
from platforms2.core.ports import PublicationRepository, TargetRepository
from platforms2.core.publications import CreatedPublication, CreatedTarget, NewPublication, TargetStatus
from social.models import SocialAccount

from .models import Publication, PublicationTarget


class DjangoTargetRepository(TargetRepository):
    @sync_to_async
    def job_of(self, target_id: int) -> PublishJob:
        target = PublicationTarget.objects.select_related(
            "publication", "publication__asset", "social_account"
        ).get(pk=target_id)
        return self._job_from(target)

    @staticmethod
    def _job_from(target: PublicationTarget) -> PublishJob:
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
    def claim(self, target_id: int, now: datetime) -> bool:
        return bool(
            PublicationTarget.objects.filter(pk=target_id, status=TargetStatus.QUEUED).update(
                status=TargetStatus.VALIDATING,
                started_at=Coalesce("started_at", Value(now)),
                last_activity_at=now,
            )
        )

    @sync_to_async
    def start_attempt(self, target_id: int, now: datetime) -> None:
        PublicationTarget.objects.filter(pk=target_id).update(
            attempt_count=F("attempt_count") + 1, error=None, last_activity_at=now
        )

    @sync_to_async
    def update(self, target_id: int, **fields) -> None:
        PublicationTarget.objects.filter(pk=target_id).update(**fields)

    @sync_to_async
    def cancel_requested(self, target_id: int) -> bool:
        return PublicationTarget.objects.filter(pk=target_id, cancel_requested=True).exists()

    @sync_to_async
    def claim_confirmation(self, target_id: int, now: datetime) -> bool:
        waiting = PublicationTarget.objects.filter(pk=target_id, status=TargetStatus.PROCESSING)
        row = waiting.values("last_activity_at").first()
        if row is None:
            return False
        return bool(waiting.filter(last_activity_at=row["last_activity_at"]).update(last_activity_at=now))

    @sync_to_async
    def take_due(self, platforms: Iterable[PlatformType], now: datetime, dispatched_before: datetime) -> list[int]:
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
    def take_stalled_confirmations(self, now: datetime, stalled_before: datetime) -> list[int]:
        stalled = Q(status=TargetStatus.PROCESSING, last_activity_at__lt=stalled_before)
        candidates = PublicationTarget.objects.filter(stalled).values_list("pk", flat=True)
        return [
            pk for pk in list(candidates) if PublicationTarget.objects.filter(stalled, pk=pk).update(last_activity_at=now)
        ]

    @sync_to_async
    def fail_abandoned(self, now: datetime, abandoned_before: datetime, failure: dict) -> list[int]:
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
    def ensure_owned(self, owner_id: int, target_id: int) -> None:
        if not PublicationTarget.objects.filter(publication__user_id=owner_id, pk=target_id).exists():
            raise NotFound()

    @sync_to_async
    def status_of(self, target_id: int) -> TargetStatus:
        return TargetStatus(PublicationTarget.objects.values_list("status", flat=True).get(pk=target_id))

    @sync_to_async
    def request_cancel(self, target_id: int, now: datetime) -> None:
        PublicationTarget.objects.filter(pk=target_id).update(cancel_requested=True)
        PublicationTarget.objects.filter(pk=target_id, status=TargetStatus.QUEUED).update(
            status=TargetStatus.CANCELLED, finished_at=now
        )

    @sync_to_async
    def reset_for_retry(self, target_id: int) -> None:
        PublicationTarget.objects.filter(pk=target_id).update(
            status=TargetStatus.QUEUED,
            cancel_requested=False,
            error=None,
            finished_at=None,
            last_activity_at=None,
            uploaded_media_id="",
            confirmation_state=None,
        )


class DjangoPublicationRepository(PublicationRepository):
    @sync_to_async
    def asset_ready(self, owner_id: int, asset_id: int) -> bool:
        return MediaAsset.objects.filter(user_id=owner_id, pk=asset_id, status=MediaAsset.Status.READY).exists()

    @sync_to_async
    def daily_limit(self, owner_id: int) -> int:
        return get_user_model().objects.values_list("max_publications_per_day", flat=True).get(pk=owner_id)

    @sync_to_async
    def create_within_limit(
        self, publication: NewPublication, since: datetime, limit: int
    ) -> CreatedPublication | None:
        with transaction.atomic():
            if Publication.objects.filter(user_id=publication.owner_id, created_at__gte=since).count() >= limit:
                return None
            return self._create(publication)

    @staticmethod
    def _create(publication: NewPublication) -> CreatedPublication:
        asset = MediaAsset.objects.get(user_id=publication.owner_id, pk=publication.asset_id)
        row = Publication.objects.create(
            user_id=publication.owner_id,
            asset=asset,
            title=publication.title,
            description=publication.description,
            hashtags=list(publication.hashtags),
            publish_at=publication.publish_at,
        )
        targets = []
        for target in publication.targets:
            account = SocialAccount.objects.get(
                user_id=publication.owner_id, pk=target.account_id, platform=target.platform
            )
            created = PublicationTarget.objects.create(
                publication=row,
                platform=target.platform,
                social_account=account,
                settings=dict(target.settings),
                total_bytes=asset.size_bytes,
            )
            targets.append(CreatedTarget(created.pk, PlatformType(created.platform)))
        return CreatedPublication(row.pk, row.publish_at, tuple(targets))
