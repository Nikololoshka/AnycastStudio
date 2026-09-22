"""Creating a publication and steering it afterwards."""

import logging

from django.db import transaction
from django.utils import timezone

from media.models import MediaAsset
from social.models import SocialAccount

from .models import Publication, PublicationTarget

logger = logging.getLogger(__name__)

Status = PublicationTarget.Status


class DailyLimitReached(Exception):
    def __init__(self, limit: int):
        super().__init__("daily limit reached")
        self.limit = limit


def published_today(user) -> int:
    since = timezone.now() - timezone.timedelta(days=1)
    return Publication.objects.filter(user=user, created_at__gte=since).count()


def check_can_publish(user) -> None:
    """The YouTube Data API allows roughly six uploads a day on the default
    quota, for the whole project rather than per person. Refusing here gives a
    reason; letting it through gives a 403 from Google that nobody can act on."""
    limit = user.quota.max_publications_per_day
    used = published_today(user)
    if used >= limit:
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


def dispatch(publication: Publication) -> None:
    """Hand every queued target to the worker.

    Called after the transaction commits, so the worker cannot pick up a row
    that is not visible to it yet — which on SQLite it would not be.
    """
    from .tasks import run_target

    for target in publication.targets.filter(status=Status.QUEUED):
        transaction.on_commit(lambda pk=target.pk: run_target.delay(pk))


def request_cancel(target: PublicationTarget) -> bool:
    """Ask a running target to stop. The worker notices between chunks."""
    if not target.is_active:
        return False

    PublicationTarget.objects.filter(pk=target.pk).update(cancel_requested=True)
    if target.status == Status.QUEUED:
        # Nothing has picked it up, so nobody would ever see the flag.
        PublicationTarget.objects.filter(pk=target.pk, status=Status.QUEUED).update(
            status=Status.CANCELLED, finished_at=timezone.now()
        )
    return True


def retry(target: PublicationTarget) -> bool:
    """Queue a failed or cancelled target again.

    Deliberately manual. Half of what makes a publication fail — a rejected
    file, a revoked scope, an exhausted quota — does not improve on its own,
    and each retry spends quota that cannot be recovered. What was already
    uploaded is kept, so a retry continues rather than starts over.
    """
    if target.status not in (Status.FAILED, Status.CANCELLED):
        return False

    from .tasks import run_target

    PublicationTarget.objects.filter(pk=target.pk).update(
        status=Status.QUEUED,
        cancel_requested=False,
        error=None,
        finished_at=None,
    )
    transaction.on_commit(lambda: run_target.delay(target.pk))
    return True
