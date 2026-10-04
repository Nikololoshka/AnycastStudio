from datetime import datetime

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.db import transaction

from media.models import MediaAsset
from platforms.core import PlatformType
from services.core.ports import PublicationRepository
from services.core.publications import CreatedPublication, CreatedTarget, NewPublication
from social.models import SocialAccount

from ..models import Publication, PublicationTarget


class DjangoPublicationRepository(PublicationRepository):
    @sync_to_async
    def is_asset_ready(self, owner_id: int, asset_id: int) -> bool:
        return MediaAsset.objects.filter(user_id=owner_id, pk=asset_id, status=MediaAsset.Status.READY).exists()

    @sync_to_async
    def get_daily_publication_limit(self, owner_id: int) -> int:
        return get_user_model().objects.values_list("max_publications_per_day", flat=True).get(pk=owner_id)

    @sync_to_async
    def create_publication_within_limit(
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
