from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from platforms.core.auth.account import AccountRecord
from platforms.core.capabilities import Capabilities, Scheduling, ValidationResult, Validator
from platforms.core.errors import NeedsFreshToken, NotFound
from platforms.core.platform import Platform
from platforms.core.ports import (
    AccessTokens,
    AccountRepository,
    Clock,
    PublicationRepository,
    TargetRepository,
    TaskQueue,
    UnitOfWork,
)
from platforms.core.publishing import (
    Confirmation,
    MediaInfo,
    NotReady,
    PublicationDraft,
    Published,
    Publisher,
    PublishJob,
    TargetStatus,
)
from platforms.core.publishing.request import CreatedPublication, CreatedTarget, NewPublication
from platforms.registry import PlatformRegistry

START = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


class FakeClock(Clock):
    def __init__(self, now: datetime = START):
        self.current = now

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta


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

    def job_of(self, target_id: int) -> PublishJob:
        return self.rows[target_id].job

    def claim(self, target_id: int, now: datetime, abandoned_before: datetime) -> bool:
        row = self.rows[target_id]
        abandoned = row.status in (TargetStatus.VALIDATING, TargetStatus.UPLOADING, TargetStatus.PUBLISHING) and (
            row.last_activity_at is not None and row.last_activity_at < abandoned_before
        )
        if row.status != TargetStatus.QUEUED and not abandoned:
            return False
        row.status = TargetStatus.VALIDATING
        row.last_activity_at = now
        return True

    def start_attempt(self, target_id: int, now: datetime) -> None:
        self.rows[target_id].attempt_count += 1

    def update(self, target_id: int, **fields) -> None:
        row = self.rows[target_id]
        self.history.append(dict(fields))
        if "status" in fields:
            row.status = TargetStatus(fields["status"])
        if "last_activity_at" in fields:
            row.last_activity_at = fields["last_activity_at"]
        if "resume_state" in fields:
            row.job = replace(row.job, resume_state=fields["resume_state"])
        if "uploaded_media_id" in fields:
            row.job = replace(row.job, uploaded_media_id=fields["uploaded_media_id"])
        row.fields.update(fields)

    def cancel_requested(self, target_id: int) -> bool:
        return self.rows[target_id].cancel_requested

    def claim_confirmation(self, target_id: int, now: datetime) -> bool:
        row = self.rows[target_id]
        if row.status != TargetStatus.PROCESSING:
            return False
        row.last_activity_at = now
        return True

    def take_due(self, platforms: Iterable[str], now: datetime, dispatched_before: datetime) -> list[int]:
        return []

    def take_stalled_confirmations(self, now: datetime, stalled_before: datetime) -> list[int]:
        return []

    def ensure_owned(self, owner_id: int, target_id: int) -> None:
        if target_id not in self.rows:
            raise NotFound()

    def status_of(self, target_id: int) -> TargetStatus:
        return self.rows[target_id].status

    def request_cancel(self, target_id: int, now: datetime) -> None:
        row = self.rows[target_id]
        row.cancel_requested = True
        if row.status == TargetStatus.QUEUED:
            row.status = TargetStatus.CANCELLED

    def reset_for_retry(self, target_id: int) -> None:
        row = self.rows[target_id]
        row.status = TargetStatus.QUEUED
        row.cancel_requested = False
        row.last_activity_at = None


class FakeQueue(TaskQueue):
    def __init__(self):
        self.runs: list[int] = []
        self.confirmations: list[tuple[int, int]] = []

    def run_target(self, target_id: int) -> None:
        self.runs.append(target_id)

    def confirm_now(self, target_id: int) -> None:
        self.confirmations.append((target_id, 0))

    def confirm_later(self, target_id: int, delay_seconds: int) -> None:
        self.confirmations.append((target_id, delay_seconds))


class FakeTokens(AccessTokens):
    def __init__(self):
        self.refreshed = 0

    def valid(self, account_id: int) -> str:
        return "stale" if self.refreshed == 0 else "fresh"

    def refresh(self, account_id: int) -> str:
        self.refreshed += 1
        return "fresh"


class FakeValidator(Validator):
    def __init__(self, errors: list[str] | None = None):
        self.errors = errors or []

    def validate(self, draft: PublicationDraft) -> ValidationResult:
        return ValidationResult(valid=not self.errors, errors=self.errors)


class FakePublisher(Publisher):
    label = "Fake"

    def __init__(self):
        self.published = Published(TargetStatus.COMPLETED, "https://fake.test/1")
        self.confirmations: list[Confirmation] = []
        self.commit_outcome: Published | Exception = Published(TargetStatus.COMPLETED, "https://fake.test/post")
        self.uncertain: Published | None = None
        self.upload_failures: list[Exception] = []
        self.tokens_seen: list[str] = []
        self.resumed_from: list[dict | None] = []

    def upload(self, job: PublishJob, access_token: str, on_progress, should_cancel) -> str:
        self.tokens_seen.append(access_token)
        self.resumed_from.append(job.resume_state)
        if self.upload_failures:
            raise self.upload_failures.pop(0)
        on_progress(job.draft.media.size_bytes, job.draft.media.size_bytes, {"offset": job.draft.media.size_bytes})
        return "media-1"

    def publish(self, job: PublishJob, media_id: str, access_token: str) -> Published:
        return self.published

    def confirm(self, job: PublishJob, access_token: str) -> Confirmation:
        return self.confirmations.pop(0) if self.confirmations else NotReady()

    def commit(self, job: PublishJob, access_token: str) -> Published:
        if isinstance(self.commit_outcome, Exception):
            raise self.commit_outcome
        return self.commit_outcome

    def resolve_uncertain(self, job: PublishJob, access_token: str) -> Published | None:
        return self.uncertain


def rejected(state: dict | None) -> NeedsFreshToken:
    return NeedsFreshToken(state, "The connection expired")


def fake_catalog(publisher: Publisher, validator: Validator) -> PlatformRegistry:
    capabilities = Capabilities(
        label="Fake", scheduling=Scheduling.DEFERRED_UPLOAD, title=True, description=True, hashtags=True, drafts=False
    )
    return PlatformRegistry(
        [Platform("fake", "Fake", capabilities, provider=None, publisher=publisher, validator=validator)]
    )


def fake_job(video_path: Path, target_id: int = 1, **overrides) -> PublishJob:
    draft = PublicationDraft("A video", "About things", ("one",), MediaInfo(1024, "video/mp4"))
    job = PublishJob(
        target_id=target_id,
        platform="fake",
        account_id=7,
        external_id="ext-1",
        draft=draft,
        video_path=video_path,
    )
    return replace(job, **overrides)


class FakeAccounts(AccountRepository):
    def __init__(self, *accounts: AccountRecord):
        self.accounts = {account.id: account for account in accounts}

    def owned_accounts(self, owner_id: int) -> dict[int, AccountRecord]:
        return dict(self.accounts)


class FakePublications(PublicationRepository):
    def __init__(self, limit: int = 5, created: int = 0):
        self.limit = limit
        self.created = created
        self.rows: list[NewPublication] = []

    def asset_ready(self, owner_id: int, asset_id: int) -> bool:
        return asset_id == 1

    def daily_limit(self, owner_id: int) -> int:
        return self.limit

    def created_since(self, owner_id: int, since: datetime) -> int:
        return self.created

    def create(self, publication: NewPublication) -> CreatedPublication:
        self.rows.append(publication)
        targets = tuple(CreatedTarget(index + 1, target.platform) for index, target in enumerate(publication.targets))
        return CreatedPublication(len(self.rows), publication.publish_at, targets)


class FakeUnitOfWork(UnitOfWork):
    def __init__(self):
        self.committed: list = []

    @contextmanager
    def atomic(self):
        yield

    def on_commit(self, action) -> None:
        self.committed.append(action)
        action()
