import logging
from datetime import datetime, timedelta

from ..auth.account import AccountStatus
from ..errors import AccountNeedsReauth, Conflict, Invalid, LimitReached, NotFound
from ..platform import PlatformCatalog
from ..ports import AccountRepository, Clock, PublicationRepository, TargetRepository, TaskQueue, UnitOfWork
from .request import NewPublication
from .status import TargetStatus

logger = logging.getLogger(__name__)

RETRYABLE = (TargetStatus.FAILED, TargetStatus.CANCELLED)


class PublicationService:
    LIMIT_WINDOW = timedelta(days=1)

    def __init__(
        self,
        publications: PublicationRepository,
        targets: TargetRepository,
        accounts: AccountRepository,
        catalog: PlatformCatalog,
        queue: TaskQueue,
        unit_of_work: UnitOfWork,
        clock: Clock,
    ):
        self._publications = publications
        self._targets = targets
        self._accounts = accounts
        self._catalog = catalog
        self._queue = queue
        self._unit_of_work = unit_of_work
        self._clock = clock

    def create(self, publication: NewPublication) -> int:
        now = self._clock.now()
        if not self._publications.asset_ready(publication.owner_id, publication.asset_id):
            raise NotFound("media_asset")
        if publication.publish_at and publication.publish_at <= now:
            raise Invalid("publishAt", "must be in the future")
        self._check_accounts(publication)

        with self._unit_of_work.atomic():
            self._check_daily_limit(publication.owner_id, now)
            created = self._publications.create(publication)
            logger.info("Publication %s created with %d targets", created.id, len(created.targets))
            for target in created.targets:
                self._hand_to_worker(target.id, target.platform, created.publish_at)
        return created.id

    def cancel(self, target_id: int) -> None:
        status = self._targets.status_of(target_id)
        if not status.is_active or status == TargetStatus.PROCESSING:
            raise Conflict("not_running")
        self._targets.request_cancel(target_id, self._clock.now())

    def retry(self, target_id: int) -> None:
        if self._targets.status_of(target_id) not in RETRYABLE:
            raise Conflict("not_retryable")
        self._targets.reset_for_retry(target_id)
        job = self._targets.job_of(target_id)
        self._hand_to_worker(target_id, job.platform, job.publish_at)

    def _check_accounts(self, publication: NewPublication) -> None:
        accounts = self._accounts.owned_accounts(publication.owner_id)
        for target in publication.targets:
            account = accounts.get(target.account_id)
            if account is None or account.platform != target.platform:
                raise NotFound("social_account")
            if account.status != AccountStatus.ACTIVE:
                raise AccountNeedsReauth(account.platform)

    def _check_daily_limit(self, owner_id: int, now: datetime) -> None:
        limit = self._publications.daily_limit(owner_id)
        if self._publications.created_since(owner_id, now - self.LIMIT_WINDOW) >= limit:
            raise LimitReached("daily_limit", limit)

    def _hand_to_worker(self, target_id: int, platform: str, publish_at: datetime | None) -> None:
        if self._waits_for_publish_at(platform, publish_at):
            logger.info("Target %s waits for its publish time", target_id)
            return
        self._unit_of_work.on_commit(lambda: self._queue.run_target(target_id))

    def _waits_for_publish_at(self, platform: str, publish_at: datetime | None) -> bool:
        deferred = platform in self._catalog.deferring_upload()
        return deferred and publish_at is not None and publish_at > self._clock.now()

