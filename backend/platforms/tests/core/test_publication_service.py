from datetime import timedelta
from pathlib import Path

from django.test import SimpleTestCase

from platforms.core.auth.account import AccountRecord, AccountStatus
from platforms.core.errors import AccountNeedsReauth, Conflict, Invalid, LimitReached, NotFound
from platforms.core.publishing import TargetStatus
from platforms.core.publishing.request import NewPublication, NewTarget
from platforms.core.publishing.service import PublicationService

from ..fakes.auth import FakeAccounts
from ..fakes.clock import FakeClock
from ..fakes.publishing import (
    FakePublications,
    FakePublisher,
    FakeQueue,
    FakeTargets,
    FakeUnitOfWork,
    FakeValidator,
    fake_catalog,
    fake_job,
)


class PublicationServiceScenarios(SimpleTestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.targets = FakeTargets()
        self.queue = FakeQueue()
        self.publications = FakePublications()
        self.accounts = FakeAccounts(AccountRecord(7, "fake", AccountStatus.ACTIVE))
        self.service = PublicationService(
            self.publications,
            self.targets,
            self.accounts,
            fake_catalog(FakePublisher(), FakeValidator()),
            self.queue,
            FakeUnitOfWork(),
            self.clock,
        )

    def new_publication(self, **overrides) -> NewPublication:
        values = {
            "owner_id": 1,
            "asset_id": 1,
            "title": "A video",
            "description": "",
            "hashtags": (),
            "publish_at": None,
            "targets": (NewTarget("fake", 7),),
        }
        return NewPublication(**{**values, **overrides})

    def test_a_publication_for_now_is_handed_to_the_worker(self):
        # When: a publication without a publish time is created
        self.service.create(self.new_publication())

        # Then: its target is queued for the worker
        self.assertEqual(self.queue.runs, [1])

    def test_a_later_publication_on_a_platform_without_scheduling_waits(self):
        # When: the platform uploads only when the time comes
        self.service.create(self.new_publication(publish_at=self.clock.now() + timedelta(hours=1)))

        # Then: nothing is queued yet
        self.assertEqual(self.queue.runs, [])

    def test_a_publish_time_in_the_past_is_refused(self):
        with self.assertRaises(Invalid):
            self.service.create(self.new_publication(publish_at=self.clock.now() - timedelta(minutes=1)))

    def test_an_asset_that_is_not_ready_is_not_found(self):
        with self.assertRaises(NotFound):
            self.service.create(self.new_publication(asset_id=2))

    def test_somebody_elses_account_is_not_found(self):
        with self.assertRaises(NotFound):
            self.service.create(self.new_publication(targets=(NewTarget("fake", 8),)))

    def test_an_account_that_must_reconnect_is_refused(self):
        # Given: the account lost its authorization
        self.accounts.accounts[7] = AccountRecord(7, "fake", AccountStatus.NEEDS_REAUTH)

        # When / Then: the person is told to reconnect it
        with self.assertRaises(AccountNeedsReauth):
            self.service.create(self.new_publication())

    def test_the_daily_limit_stops_the_next_publication(self):
        # Given: the person already published as much as allowed today
        self.publications.created = self.publications.limit

        # When / Then: the next one is refused and nothing is stored
        with self.assertRaises(LimitReached):
            self.service.create(self.new_publication())
        self.assertEqual(self.publications.rows, [])

    def test_a_target_waiting_for_the_platform_cannot_be_cancelled(self):
        self.targets.add(fake_job(Path("clip.mp4")), status=TargetStatus.PROCESSING)

        with self.assertRaises(Conflict):
            self.service.cancel(1)

    def test_a_queued_target_is_cancelled_at_once(self):
        row = self.targets.add(fake_job(Path("clip.mp4")))

        self.service.cancel(1)

        self.assertEqual(row.status, TargetStatus.CANCELLED)

    def test_only_a_failed_or_cancelled_target_is_retried(self):
        self.targets.add(fake_job(Path("clip.mp4")), status=TargetStatus.COMPLETED)

        with self.assertRaises(Conflict):
            self.service.retry(1)

    def test_a_failed_target_is_queued_again(self):
        row = self.targets.add(fake_job(Path("clip.mp4")), status=TargetStatus.FAILED)

        self.service.retry(1)

        self.assertEqual(row.status, TargetStatus.QUEUED)
        self.assertEqual(self.queue.runs, [1])
