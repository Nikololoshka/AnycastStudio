from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from .models import PublicationTarget
from .publishers import PUBLISHERS

Status = PublicationTarget.Status

REDISPATCH_AFTER = timedelta(minutes=15)


def deferred_platforms() -> list[str]:
    return [
        name for name, publisher in PUBLISHERS.items() if publisher.capabilities().scheduling == "deferredUpload"
    ]


def waits_for_publish_at(target: PublicationTarget) -> bool:
    publish_at = target.publication.publish_at
    return publish_at is not None and publish_at > timezone.now() and target.platform in deferred_platforms()


def take_due_targets() -> list[int]:
    now = timezone.now()
    not_recently_dispatched = Q(last_activity_at__isnull=True) | Q(last_activity_at__lt=now - REDISPATCH_AFTER)
    due = PublicationTarget.objects.filter(
        not_recently_dispatched,
        status=Status.QUEUED,
        platform__in=deferred_platforms(),
        publication__publish_at__lte=now,
    ).values_list("pk", flat=True)
    return [
        pk
        for pk in list(due)
        if PublicationTarget.objects.filter(not_recently_dispatched, pk=pk, status=Status.QUEUED).update(
            last_activity_at=now
        )
    ]
