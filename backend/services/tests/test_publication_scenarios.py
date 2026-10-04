import shutil
import tempfile
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest import IsolatedAsyncioTestCase

from platforms.core import (
    AwaitingConfirmation,
    NotReady,
    PlatformError,
    PlatformFailure,
    Published,
    ReadyToCommit,
    Scheduled,
)
from platforms.tests.fakes.platform import FAKE, FakePlatform, FakeRegistry
from services.core.accounts import AccountRecord, AccountStatus
from services.core.domain import AccountNeedsReauth, Conflict, Invalid, LimitReached, NotFound
from services.core.publications import NewPublication, NewTarget, TargetStatus
from services.usecases.publications import (
    CommitGuard,
    ConfirmationPoller,
    PublicationPipeline,
    PublicationService,
    StaleTargetSweeper,
    TargetWriter,
)

from .fakes.accounts import FakeAccounts
from .fakes.clock import FakeClock
from .fakes.publishing import FakePublications, FakeQueue, FakeTargets, FakeTokens, fake_job

COMMIT_STARTED = CommitGuard.COMMIT_STARTED


class PublicationScenarioBase(IsolatedAsyncioTestCase):
    def setUp(self):
        folder = Path(tempfile.mkdtemp(prefix="anycast-pipeline-test-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        self.video = folder / "clip.mp4"
        self.video.write_bytes(b"0" * 1024)

        self.clock = FakeClock()
        self.targets = FakeTargets()
        self.queue = FakeQueue()
        self.tokens = FakeTokens()
        self.platform = FakePlatform()
        self.publishing = self.platform.publishing
        registry = FakeRegistry(self.platform)
        writer = TargetWriter(self.targets, self.clock)
        self.pipeline = PublicationPipeline(self.targets, registry, self.tokens, self.queue, writer)
        commits = CommitGuard(writer, self.tokens, registry)
        self.poller = ConfirmationPoller(self.targets, registry, self.tokens, self.queue, writer, commits)
        self.sweeper = StaleTargetSweeper(self.targets, self.clock)

    def given_target(self, **job):
        return self.targets.add(fake_job(self.video, **job))

    def given_processing(self, **state):
        confirming = {"confirming_since": self.clock.now().isoformat(), "polls": 0, **state}
        return self.targets.add(
            fake_job(self.video, media_id="media-1", confirmation_state=confirming), status=TargetStatus.PROCESSING
        )


class PipelineScenarios(PublicationScenarioBase):
    async def test_a_queued_target_is_uploaded_and_published(self):
        # Given: a queued target on a platform that publishes at once
        row = self.given_target()

        # When: the worker runs it
        status = await self.pipeline.run(1)

        # Then: it is completed with the link, full progress and one attempt
        self.assertEqual(status, TargetStatus.COMPLETED)
        self.assertEqual(row.fields["published_url"], "https://fake.test/1")
        self.assertEqual(row.fields["progress"], 100)
        self.assertEqual(row.job.media_id, "media-1")
        self.assertEqual(row.attempt_count, 1)

    async def test_progress_is_written_on_whole_percents(self):
        self.given_target()

        await self.pipeline.run(1)

        written = [entry["progress"] for entry in self.targets.history if "progress" in entry]
        self.assertEqual(written, [0, 25, 50, 75, 100, 100])

    async def test_a_target_already_taken_is_left_alone(self):
        # Given: a target another worker is uploading
        self.given_target().status = TargetStatus.UPLOADING

        # When / Then: the second worker takes nothing, even a target silent for long
        self.clock.advance(timedelta(hours=1))
        self.assertIsNone(await self.pipeline.run(1))
        self.assertEqual(self.publishing.tokens_seen, [])

    async def test_a_cancel_before_the_start_sends_nothing(self):
        self.given_target().cancel_requested = True

        status = await self.pipeline.run(1)

        self.assertEqual(status, TargetStatus.CANCELLED)
        self.assertEqual(self.publishing.tokens_seen, [])

    async def test_a_cancel_during_the_upload_stops_it(self):
        # Given: the person cancels while the second chunk goes out
        row = self.given_target()

        def cancel_at(chunk: int) -> None:
            if chunk == 2:
                row.cancel_requested = True

        self.publishing.on_chunk = cancel_at

        # When: the worker runs it
        status = await self.pipeline.run(1)

        # Then: it is cancelled without a media id
        self.assertEqual(status, TargetStatus.CANCELLED)
        self.assertEqual(row.job.media_id, "")

    async def test_a_draft_the_platform_refuses_fails_with_the_reasons(self):
        row = self.given_target()
        self.platform.validator.errors = ("titleTooLong", "fileTooLarge")

        status = await self.pipeline.run(1)

        self.assertEqual(status, TargetStatus.FAILED)
        self.assertEqual(row.fields["error"]["failure"], PlatformFailure.INVALID)
        self.assertEqual(row.fields["error"]["details"], "titleTooLong,fileTooLarge")
        self.assertEqual(self.publishing.tokens_seen, [])

    async def test_a_missing_file_fails_as_media_missing(self):
        row = self.given_target()
        self.video.unlink()

        await self.pipeline.run(1)

        self.assertEqual(row.fields["error"]["failure"], PlatformFailure.MEDIA_MISSING)

    async def test_a_rejected_token_is_refreshed_and_the_upload_starts_again(self):
        # Given: the platform rejects the first token
        self.given_target()
        self.publishing.upload_failures = [PlatformError(PlatformFailure.TOKEN_REJECTED, "expired")]

        # When: the worker runs it
        status = await self.pipeline.run(1)

        # Then: the second attempt used a fresh token
        self.assertEqual(status, TargetStatus.COMPLETED)
        self.assertEqual(self.publishing.tokens_seen, ["stale", "fresh"])

    async def test_a_platform_refusal_is_not_retried(self):
        row = self.given_target()
        self.publishing.upload_failures = [PlatformError(PlatformFailure.RATE_LIMITED, "quotaExceeded")]

        status = await self.pipeline.run(1)

        self.assertEqual(status, TargetStatus.FAILED)
        self.assertEqual(row.fields["error"]["failure"], PlatformFailure.RATE_LIMITED)
        self.assertEqual(self.publishing.tokens_seen, ["stale"])

    async def test_an_unexpected_exception_reports_only_its_class(self):
        row = self.given_target()
        self.publishing.upload_failures = [RuntimeError("https://api.test/?token=secret")]

        await self.pipeline.run(1)

        self.assertEqual(row.fields["error"]["failure"], PlatformFailure.UNEXPECTED)
        self.assertEqual(row.fields["error"]["message"], "RuntimeError")

    async def test_a_scheduled_video_is_left_to_the_platform(self):
        row = self.given_target()
        self.publishing.outcome = Scheduled("https://fake.test/later")

        status = await self.pipeline.run(1)

        self.assertEqual(status, TargetStatus.SCHEDULED)
        self.assertEqual(row.fields["published_url"], "https://fake.test/later")
        self.assertEqual(self.queue.confirmations, [])

    async def test_a_platform_that_confirms_later_gets_its_first_poll_scheduled(self):
        # Given: a platform that processes the video after the upload
        row = self.given_target()
        self.publishing.outcome = AwaitingConfirmation({"container": "c-1"})

        # When: the worker runs it
        status = await self.pipeline.run(1)

        # Then: it waits with the platform's state, knows since when, and the first poll is queued
        self.assertEqual(status, TargetStatus.PROCESSING)
        self.assertEqual(
            row.job.confirmation_state,
            {"container": "c-1", "confirming_since": self.clock.now().isoformat(), "polls": 0},
        )
        self.assertEqual(self.queue.confirmations, [(1, ConfirmationPoller.POLL_DELAYS_SECONDS[0])])


class StaleTargetScenarios(PublicationScenarioBase):
    async def test_a_target_silent_for_too_long_fails_and_asks_to_publish_again(self):
        # Given: a target stuck uploading since before the abandon threshold
        row = self.given_target()
        row.status = TargetStatus.UPLOADING
        row.last_activity_at = self.clock.now()
        self.clock.advance(StaleTargetSweeper.ABANDONED_AFTER * 2)

        # When: the sweep runs
        swept = await self.sweeper.sweep()

        # Then: it failed with a reason the person can act on
        self.assertEqual(swept, 1)
        self.assertEqual(row.status, TargetStatus.FAILED)
        self.assertIn("publish again", row.fields["error"]["message"])

    async def test_a_target_worked_on_recently_is_kept(self):
        row = self.given_target()
        row.status = TargetStatus.UPLOADING
        row.last_activity_at = self.clock.now()

        self.assertEqual(await self.sweeper.sweep(), 0)
        self.assertEqual(row.status, TargetStatus.UPLOADING)

    async def test_a_target_waiting_for_the_platform_is_not_swept(self):
        row = self.given_processing()
        row.last_activity_at = self.clock.now()
        self.clock.advance(StaleTargetSweeper.ABANDONED_AFTER * 2)

        self.assertEqual(await self.sweeper.sweep(), 0)
        self.assertEqual(row.status, TargetStatus.PROCESSING)


class ConfirmationScenarios(PublicationScenarioBase):
    async def test_a_platform_still_working_is_asked_again_later(self):
        row = self.given_processing()
        self.publishing.confirmations = [NotReady()]

        delay = await self.poller.confirm(1)

        self.assertEqual(delay, ConfirmationPoller.POLL_DELAYS_SECONDS[1])
        self.assertEqual(row.job.confirmation_state["polls"], 1)
        self.assertEqual(self.queue.confirmations, [(1, delay)])

    async def test_a_target_not_waiting_is_not_asked_about(self):
        self.given_target(media_id="media-1")

        self.assertIsNone(await self.poller.confirm(1))
        self.assertEqual(self.queue.confirmations, [])

    async def test_a_confirmed_publish_completes_the_target(self):
        row = self.given_processing()
        self.publishing.confirmations = [Published("https://fake.test/done")]

        await self.poller.confirm(1)

        self.assertEqual(row.status, TargetStatus.COMPLETED)
        self.assertEqual(row.fields["published_url"], "https://fake.test/done")

    async def test_a_platform_refusal_fails_the_target(self):
        row = self.given_processing()
        self.publishing.confirmations = [PlatformError(PlatformFailure.FILE_REJECTED, "Bad codec", "failed")]

        await self.poller.confirm(1)

        self.assertEqual(row.status, TargetStatus.FAILED)
        self.assertEqual(
            row.fields["error"], {"failure": PlatformFailure.FILE_REJECTED, "message": "Bad codec", "details": "failed"}
        )

    async def test_a_platform_silent_past_the_window_fails_the_target(self):
        row = self.given_processing()
        self.clock.advance(ConfirmationPoller.CONFIRM_WITHIN + timedelta(seconds=1))

        delay = await self.poller.confirm(1)

        self.assertIsNone(delay)
        self.assertEqual(row.status, TargetStatus.FAILED)
        self.assertEqual(row.fields["error"]["failure"], PlatformFailure.UNCONFIRMED)

    async def test_a_window_start_stored_as_a_timestamp_is_still_understood(self):
        row = self.given_processing()
        row.job = replace(row.job, confirmation_state={"confirming_since": self.clock.now().timestamp(), "polls": 3})
        self.clock.advance(ConfirmationPoller.CONFIRM_WITHIN + timedelta(seconds=1))

        self.assertIsNone(await self.poller.confirm(1))
        self.assertEqual(row.status, TargetStatus.FAILED)

    async def test_a_ready_commit_is_marked_before_it_is_sent(self):
        # Given: the platform is ready and the final step cannot be repeated safely
        row = self.given_processing()
        self.publishing.confirmations = [ReadyToCommit()]

        # When: it is polled
        await self.poller.confirm(1)

        # Then: the mark was written before the commit, and the post is completed
        marked = [entry["confirmation_state"] for entry in self.targets.history if "confirmation_state" in entry]
        self.assertIn(COMMIT_STARTED, marked[0])
        self.assertEqual(row.status, TargetStatus.COMPLETED)
        self.assertEqual(row.fields["published_url"], "https://fake.test/post")

    async def test_an_unanswered_commit_keeps_the_mark_and_warns(self):
        # Given: the commit went out but no answer came back
        row = self.given_processing()
        self.publishing.confirmations = [ReadyToCommit()]
        self.publishing.commit_outcome = PlatformError(PlatformFailure.NETWORK, "timed out")

        # When: it is polled
        await self.poller.confirm(1)

        # Then: the target fails as possibly posted and the mark stays
        self.assertEqual(row.status, TargetStatus.FAILED)
        self.assertEqual(row.fields["error"]["failure"], PlatformFailure.UNCONFIRMED)
        self.assertIn("may have been created; check Fake", row.fields["error"]["message"])
        self.assertIn(COMMIT_STARTED, row.job.confirmation_state)
        self.assertEqual(self.publishing.commits, 1)

    async def test_a_refused_commit_clears_the_mark(self):
        row = self.given_processing()
        self.publishing.confirmations = [ReadyToCommit()]
        self.publishing.commit_outcome = PlatformError(PlatformFailure.INVALID, "Text too long")

        await self.poller.confirm(1)

        self.assertEqual(row.fields["error"]["failure"], PlatformFailure.INVALID)
        self.assertNotIn(COMMIT_STARTED, row.job.confirmation_state)

    async def test_a_rejected_token_at_commit_is_refreshed_and_the_commit_sent_again(self):
        row = self.given_processing()
        self.publishing.confirmations = [ReadyToCommit()]
        outcomes = [PlatformError(PlatformFailure.TOKEN_REJECTED, "expired"), Published("https://fake.test/post")]

        async def commit(job, access_token):
            self.publishing.commits += 1
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        self.publishing.commit = commit

        await self.poller.confirm(1)

        self.assertEqual(row.status, TargetStatus.COMPLETED)
        self.assertEqual(self.publishing.commits, 2)

    async def test_a_commit_already_started_is_not_sent_twice(self):
        row = self.given_processing(**{COMMIT_STARTED: self.clock.now().isoformat()})
        self.publishing.confirmations = [ReadyToCommit()]

        await self.poller.confirm(1)

        self.assertEqual(row.status, TargetStatus.FAILED)
        self.assertIn("may have been created", row.fields["error"]["message"])
        self.assertEqual(self.publishing.commits, 0)

    async def test_a_platform_that_can_tell_resolves_the_uncertain_commit(self):
        row = self.given_processing(**{COMMIT_STARTED: self.clock.now().isoformat()})
        self.publishing.uncertain = Published("https://fake.test/found")

        await self.poller.confirm(1)

        self.assertEqual(row.status, TargetStatus.COMPLETED)
        self.assertEqual(row.fields["published_url"], "https://fake.test/found")


class PublicationServiceScenarios(IsolatedAsyncioTestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.targets = FakeTargets()
        self.queue = FakeQueue()
        self.publications = FakePublications()
        self.accounts = FakeAccounts(AccountRecord(7, FAKE, AccountStatus.ACTIVE))
        self.service = PublicationService(
            self.publications, self.targets, self.accounts, FakeRegistry(FakePlatform()), self.queue, self.clock
        )

    def new_publication(self, **overrides) -> NewPublication:
        values = {
            "owner_id": 1,
            "asset_id": 1,
            "title": "A video",
            "description": "",
            "hashtags": (),
            "publish_at": None,
            "targets": (NewTarget(FAKE, 7),),
        }
        return NewPublication(**{**values, **overrides})

    async def test_a_publication_for_now_is_handed_to_the_worker(self):
        await self.service.create(self.new_publication())

        self.assertEqual(self.queue.runs, [1])

    async def test_a_later_publication_on_a_platform_without_scheduling_waits(self):
        await self.service.create(self.new_publication(publish_at=self.clock.now() + timedelta(hours=1)))

        self.assertEqual(self.queue.runs, [])

    async def test_a_publish_time_in_the_past_is_refused(self):
        with self.assertRaises(Invalid):
            await self.service.create(self.new_publication(publish_at=self.clock.now() - timedelta(minutes=1)))

    async def test_an_asset_that_is_not_ready_is_not_found(self):
        with self.assertRaises(NotFound):
            await self.service.create(self.new_publication(asset_id=2))

    async def test_somebody_elses_account_is_not_found(self):
        with self.assertRaises(NotFound):
            await self.service.create(self.new_publication(targets=(NewTarget(FAKE, 8),)))

    async def test_a_disconnected_account_is_not_found(self):
        self.accounts.accounts[7] = AccountRecord(7, FAKE, AccountStatus.REVOKED)

        with self.assertRaises(NotFound):
            await self.service.create(self.new_publication())

    async def test_an_account_that_must_reconnect_is_refused(self):
        self.accounts.accounts[7] = AccountRecord(7, FAKE, AccountStatus.NEEDS_REAUTH)

        with self.assertRaises(AccountNeedsReauth):
            await self.service.create(self.new_publication())

    async def test_the_daily_limit_stops_the_next_publication(self):
        self.publications.created = self.publications.limit

        with self.assertRaises(LimitReached):
            await self.service.create(self.new_publication())
        self.assertEqual(self.publications.rows, [])
        self.assertEqual(self.queue.runs, [])

    async def test_a_target_waiting_for_the_platform_cannot_be_cancelled(self):
        self.targets.add(fake_job(Path("clip.mp4")), status=TargetStatus.PROCESSING)

        with self.assertRaises(Conflict):
            await self.service.cancel(1)

    async def test_a_queued_target_is_cancelled_at_once(self):
        row = self.targets.add(fake_job(Path("clip.mp4")))

        await self.service.cancel(1)

        self.assertEqual(row.status, TargetStatus.CANCELLED)

    async def test_only_a_failed_or_cancelled_target_is_retried(self):
        self.targets.add(fake_job(Path("clip.mp4")), status=TargetStatus.COMPLETED)

        with self.assertRaises(Conflict):
            await self.service.retry(1)

    async def test_a_failed_target_is_queued_again_from_the_start(self):
        row = self.targets.add(
            fake_job(Path("clip.mp4"), media_id="media-1", confirmation_state={COMMIT_STARTED: "x"}),
            status=TargetStatus.FAILED,
        )

        await self.service.retry(1)

        self.assertEqual(row.status, TargetStatus.QUEUED)
        self.assertEqual((row.job.media_id, dict(row.job.confirmation_state)), ("", {}))
        self.assertEqual(self.queue.runs, [1])
