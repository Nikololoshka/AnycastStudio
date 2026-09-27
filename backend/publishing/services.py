import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from media.models import MediaAsset
from social.models import SocialAccount

from . import schedule
from .models import Publication, PublicationTarget
from .tasks import run_target

logger = logging.getLogger(__name__)

Status = PublicationTarget.Status


class DailyLimitReached(Exception):
    def __init__(self, limit: int):
        super().__init__("daily limit reached")
        self.limit = limit


def published_in_the_last_day(user) -> int:
    since = timezone.now() - timedelta(days=1)
    return Publication.objects.filter(user=user, created_at__gte=since).count()


def check_can_publish(user) -> None:
    limit = user.max_publications_per_day
    if published_in_the_last_day(user) >= limit:
        raise DailyLimitReached(limit)


@transaction.atomic
def create_publication(
    *, user, asset: MediaAsset, title: str, description: str, hashtags: list[str], publish_at, targets: list[dict]
) -> Publication:
    check_can_publish(user)

    publication = Publication.objects.create(
        user=user,
        asset=asset,
        title=title,
        description=description,
        hashtags=hashtags,
        publish_at=publish_at,
    )

    for entry in targets:
        account = SocialAccount.objects.get(
            user=user, pk=entry["socialAccountId"], platform=entry["platform"]
        )
        PublicationTarget.objects.create(
            publication=publication,
            platform=entry["platform"],
            social_account=account,
            settings=entry.get("settings") or {},
            total_bytes=asset.size_bytes,
        )

    logger.info("Publication %s created with %d targets", publication.pk, len(targets))
    return publication


def _hand_to_worker(target: PublicationTarget) -> None:
    if schedule.waits_for_publish_at(target):
        logger.info("Target %s waits for its publish time", target.pk)
        return
    transaction.on_commit(lambda: run_target.delay(target.pk))


def dispatch(publication: Publication) -> None:
    for target in publication.targets.filter(status=Status.QUEUED).select_related("publication"):
        _hand_to_worker(target)


def request_cancel(target: PublicationTarget) -> bool:
    if not target.is_active:
        return False

    PublicationTarget.objects.filter(pk=target.pk).update(cancel_requested=True)
    PublicationTarget.objects.filter(pk=target.pk, status=Status.QUEUED).update(
        status=Status.CANCELLED, finished_at=timezone.now()
    )
    return True


def retry(target: PublicationTarget) -> bool:
    if target.status not in (Status.FAILED, Status.CANCELLED):
        return False

    PublicationTarget.objects.filter(pk=target.pk).update(
        status=Status.QUEUED,
        cancel_requested=False,
        error=None,
        finished_at=None,
        last_activity_at=None,
    )
    _hand_to_worker(target)
    return True
