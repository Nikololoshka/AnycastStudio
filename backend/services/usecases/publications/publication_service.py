import logging
from datetime import datetime, timedelta

from platforms.core import PlatformRegistry, PlatformType

from ...core.accounts.account_status import AccountStatus
from ...core.domain import AccountNeedsReauth, Conflict, Invalid, LimitReached, NotFound
from ...core.ports import AccountRepository, Clock, PublicationRepository, TargetRepository, TaskQueue
from ...core.publications.new_publication import NewPublication
from ...core.publications.target_status import TargetStatus

logger = logging.getLogger(__name__)


class PublicationService:
    LIMIT_WINDOW = timedelta(days=1)
    RETRYABLE = (TargetStatus.FAILED, TargetStatus.CANCELLED)

    def __init__(
        self,
        publications: PublicationRepository,
        targets: TargetRepository,
        accounts: AccountRepository,
        platforms: PlatformRegistry,
        queue: TaskQueue,
        clock: Clock,
    ):
        self._publications = publications
        self._targets = targets
        self._accounts = accounts
        self._platforms = platforms
        self._queue = queue
        self._clock = clock

    async def create(self, publication: NewPublication) -> int:
        now = self._clock.now()
        if not await self._publications.is_asset_ready(publication.owner_id, publication.asset_id):
            raise NotFound("media_asset")
        if publication.publish_at and publication.publish_at <= now:
            raise Invalid("publishAt", "must be in the future")
        await self._check_accounts(publication)

        limit = await self._publications.get_daily_publication_limit(publication.owner_id)
        created = await self._publications.create_publication_within_limit(publication, now - self.LIMIT_WINDOW, limit)
        if created is None:
            raise LimitReached("daily_limit", limit)

        logger.info("Publication %s created with %d targets", created.id, len(created.targets))
        for target in created.targets:
            await self._hand_to_worker(target.id, target.platform, created.publish_at)
        return created.id

    async def cancel(self, target_id: int) -> None:
        status = await self._targets.get_target_status(target_id)
        if not status.is_active or status == TargetStatus.PROCESSING:
            raise Conflict("not_running")
        await self._targets.request_target_cancel(target_id, self._clock.now())

    async def retry(self, target_id: int) -> None:
        if await self._targets.get_target_status(target_id) not in self.RETRYABLE:
            raise Conflict("not_retryable")
        await self._targets.reset_target_for_retry(target_id)
        job = await self._targets.get_publish_job(target_id)
        await self._hand_to_worker(target_id, job.platform, job.publish_at)

    async def _check_accounts(self, publication: NewPublication) -> None:
        accounts = await self._accounts.get_connected_accounts(publication.owner_id)
        for target in publication.targets:
            account = accounts.get(target.account_id)
            if account is None or account.platform != target.platform:
                raise NotFound("social_account")
            if account.status != AccountStatus.ACTIVE:
                raise AccountNeedsReauth(account.platform)

    async def _hand_to_worker(self, target_id: int, platform: PlatformType, publish_at: datetime | None) -> None:
        if self._waits_for_publish_at(platform, publish_at):
            logger.info("Target %s waits for its publish time", target_id)
            return
        await self._queue.run_target(target_id)

    def _waits_for_publish_at(self, platform: PlatformType, publish_at: datetime | None) -> bool:
        deferred = platform in self._platforms.deferring_upload()
        return deferred and publish_at is not None and publish_at > self._clock.now()
