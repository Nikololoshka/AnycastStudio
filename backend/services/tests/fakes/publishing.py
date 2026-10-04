from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

from platforms.core import PlatformType, PublishDraft, PublishJob, PublishMedia
from platforms.tests.fakes.platform import FAKE
from services.core.domain import NotFound
from services.core.ports import AccessTokens, PublicationRepository, TargetRepository, TaskQueue
from services.core.publications import CreatedPublication, CreatedTarget, NewPublication, TargetStatus


@dataclass
class TargetRow:
    job: PublishJob
    status: TargetStatus = TargetStatus.QUEUED
    last_activity_at: datetime | None = None
    cancel_requested: bool = False
    attempt_count: int = 0
    fields: dict = field(default_factory=dict)


class FakeTargets(TargetRepository):
    def __init__(self):
        self.rows: dict[int, TargetRow] = {}
        self.history: list[dict] = []

    def add(self, job: PublishJob, **row) -> TargetRow:
        self.rows[job.target_id] = TargetRow(job=job, **row)
        return self.rows[job.target_id]

    async def get_publish_job(self, target_id: int) -> PublishJob:
        return self.rows[target_id].job

    async def claim_queued_target(self, target_id: int, now: datetime) -> bool:
        row = self.rows[target_id]
        if row.status != TargetStatus.QUEUED:
            return False
        row.status = TargetStatus.VALIDATING
        row.last_activity_at = now
        return True

    async def start_target_attempt(self, target_id: int, now: datetime) -> None:
        self.rows[target_id].attempt_count += 1

    async def update_target(self, target_id: int, **fields) -> None:
        row = self.rows[target_id]
        self.history.append(dict(fields))
        if "status" in fields:
            row.status = TargetStatus(fields["status"])
        if "last_activity_at" in fields:
            row.last_activity_at = fields["last_activity_at"]
        if "confirmation_state" in fields:
            row.job = replace(row.job, confirmation_state=fields["confirmation_state"] or {})
        if "uploaded_media_id" in fields:
            row.job = replace(row.job, media_id=fields["uploaded_media_id"])
        row.fields.update(fields)

    async def is_cancel_requested(self, target_id: int) -> bool:
        return self.rows[target_id].cancel_requested

    async def claim_confirmation_poll(self, target_id: int, now: datetime) -> bool:
        row = self.rows[target_id]
        if row.status != TargetStatus.PROCESSING:
            return False
        row.last_activity_at = now
        return True

    async def claim_due_targets(
        self, platforms: Iterable[PlatformType], now: datetime, dispatched_before: datetime
    ) -> list[int]:
        return []

    async def claim_stalled_confirmations(self, now: datetime, stalled_before: datetime) -> list[int]:
        return []

    async def fail_abandoned_targets(self, now: datetime, abandoned_before: datetime, failure: dict) -> list[int]:
        abandoned = [
            target_id
            for target_id, row in self.rows.items()
            if row.status in TargetStatus.worked_on() and row.last_activity_at and row.last_activity_at < abandoned_before
        ]
        for target_id in abandoned:
            await self.update_target(target_id, status=TargetStatus.FAILED, error=failure, finished_at=now)
        return abandoned

    async def ensure_target_owned(self, owner_id: int, target_id: int) -> None:
        if target_id not in self.rows:
            raise NotFound()

    async def get_target_status(self, target_id: int) -> TargetStatus:
        return self.rows[target_id].status

    async def request_target_cancel(self, target_id: int, now: datetime) -> None:
        row = self.rows[target_id]
        row.cancel_requested = True
        if row.status == TargetStatus.QUEUED:
            row.status = TargetStatus.CANCELLED

    async def reset_target_for_retry(self, target_id: int) -> None:
        row = self.rows[target_id]
        row.status = TargetStatus.QUEUED
        row.cancel_requested = False
        row.last_activity_at = None
        row.job = replace(row.job, media_id="", confirmation_state={})


class FakeQueue(TaskQueue):
    def __init__(self):
        self.runs: list[int] = []
        self.confirmations: list[tuple[int, int]] = []

    async def run_target(self, target_id: int) -> None:
        self.runs.append(target_id)

    async def confirm_now(self, target_id: int) -> None:
        self.confirmations.append((target_id, 0))

    async def confirm_later(self, target_id: int, delay_seconds: int) -> None:
        self.confirmations.append((target_id, delay_seconds))


class FakeTokens(AccessTokens):
    def __init__(self):
        self.refreshed = 0

    async def valid(self, account_id: int) -> str:
        return "stale" if self.refreshed == 0 else "fresh"

    async def refresh(self, account_id: int) -> str:
        self.refreshed += 1
        return "fresh"


class FakePublications(PublicationRepository):
    def __init__(self, limit: int = 5, created: int = 0):
        self.limit = limit
        self.created = created
        self.rows: list[NewPublication] = []

    async def is_asset_ready(self, owner_id: int, asset_id: int) -> bool:
        return asset_id == 1

    async def get_daily_publication_limit(self, owner_id: int) -> int:
        return self.limit

    async def create_publication_within_limit(
        self, publication: NewPublication, since: datetime, limit: int
    ) -> CreatedPublication | None:
        if self.created >= limit:
            return None
        self.rows.append(publication)
        targets = tuple(CreatedTarget(index + 1, target.platform) for index, target in enumerate(publication.targets))
        return CreatedPublication(len(self.rows), publication.publish_at, targets)


def fake_job(video_path: Path, target_id: int = 1, **overrides) -> PublishJob:
    job = PublishJob(
        target_id=target_id,
        platform=FAKE,
        account_id=7,
        external_id="ext-1",
        draft=PublishDraft("A video", "About things", ("one",)),
        media=PublishMedia(video_path, 1024, "video/mp4"),
    )
    return replace(job, **overrides)
