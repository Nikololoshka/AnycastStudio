import shutil
import tempfile
from datetime import timedelta
from pathlib import Path

from django.test import SimpleTestCase

from platforms.core.errors import FailureType, PlatformError
from platforms.core.publishing import NotReady, Published, ReadyToCommit, TargetStatus
from platforms.core.publishing.commit import COMMIT_STARTED, CommitGuard
from platforms.core.publishing.confirmation import ConfirmationPoller
from platforms.core.publishing.failures import FailureMapper
from platforms.core.publishing.pipeline import PublicationPipeline
from platforms.core.publishing.writer import TargetWriter

from ..fakes.publishing import (
    FakeClock,
    FakePublisher,
    FakeQueue,
    FakeTargets,
    FakeTokens,
    FakeValidator,
    fake_catalog,
    fake_job,
    rejected,
)


class ScenarioBase(SimpleTestCase):
    def setUp(self):
        folder = Path(tempfile.mkdtemp(prefix="anycast-pipeline-test-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        self.video = folder / "clip.mp4"
        self.video.write_bytes(b"0" * 1024)

        self.clock = FakeClock()
        self.targets = FakeTargets()
        self.queue = FakeQueue()
        self.tokens = FakeTokens()
        self.publisher = FakePublisher()
        self.validator = FakeValidator()
        catalog = fake_catalog(self.publisher, self.validator)
        writer = TargetWriter(self.targets, self.clock)
        self.pipeline = PublicationPipeline(self.targets, catalog, self.tokens, self.queue, writer, FailureMapper())
        self.poller = ConfirmationPoller(
            self.targets, catalog, self.tokens, self.queue, writer, FailureMapper(), CommitGuard(writer, self.tokens)
        )

    def given_target(self, **job):
        return self.targets.add(fake_job(self.video, **job))

    def given_processing(self, **state):
        resume = {"confirming_since": self.clock.now().isoformat(), "polls": 0, **state}
        return self.targets.add(
            fake_job(self.video, uploaded_media_id="media-1", resume_state=resume), status=TargetStatus.PROCESSING
        )


class PipelineScenarios(ScenarioBase):
    def test_a_queued_target_is_uploaded_and_published(self):
        # Given: a queued target on a platform that publishes at once
        row = self.given_target()

        # When: the worker runs it
        status = self.pipeline.run(1)

        # Then: it is completed with the link, full progress and one attempt
        self.assertEqual(status, TargetStatus.COMPLETED)
        self.assertEqual(row.fields["published_url"], "https://fake.test/1")
        self.assertEqual(row.fields["progress"], 100)
        self.assertEqual(row.job.uploaded_media_id, "media-1")
        self.assertEqual(row.attempt_count, 1)

    def test_a_target_somebody_else_runs_is_left_alone(self):
        # Given: a target another worker touched a moment ago
        self.given_target().status = TargetStatus.UPLOADING
        self.targets.rows[1].last_activity_at = self.clock.now()

        # When / Then: the second worker takes nothing
        self.assertIsNone(self.pipeline.run(1))
        self.assertEqual(self.publisher.tokens_seen, [])

    def test_a_target_silent_for_too_long_is_taken_over(self):
        # Given: a target stuck uploading since before the abandon threshold
        row = self.given_target()
        row.status = TargetStatus.UPLOADING
        row.last_activity_at = self.clock.now()
        self.clock.advance(PublicationPipeline.ABANDONED_AFTER * 2)

        # When / Then: it is claimed again and finishes
        self.assertEqual(self.pipeline.run(1), TargetStatus.COMPLETED)

    def test_a_cancel_before_the_start_sends_nothing(self):
        # Given: the person cancelled while it was queued
        self.given_target().cancel_requested = True

        # When: the worker picks it up
        status = self.pipeline.run(1)

        # Then: it is cancelled without an upload
        self.assertEqual(status, TargetStatus.CANCELLED)
        self.assertEqual(self.publisher.tokens_seen, [])

    def test_a_draft_the_platform_refuses_fails_with_the_reasons(self):
        # Given: the platform's rules refuse the draft
        row = self.given_target()
        self.validator.errors = ["titleTooLong", "fileTooLarge"]

        # When: the worker runs it
        status = self.pipeline.run(1)

        # Then: it fails as a validation with every reason
        self.assertEqual(status, TargetStatus.FAILED)
        self.assertEqual(row.fields["error"]["type"], FailureType.VALIDATION)
        self.assertEqual(row.fields["error"]["details"], "titleTooLong,fileTooLarge")

    def test_a_missing_file_fails_as_a_file_problem(self):
        # Given: the stored video is gone
        row = self.given_target()
        self.video.unlink()

        # When: the worker runs it
        self.pipeline.run(1)

        # Then: the failure names the file
        self.assertEqual(row.fields["error"]["type"], FailureType.FILE)

    def test_a_rejected_token_is_refreshed_and_the_upload_resumes_where_it_stopped(self):
        # Given: the platform rejects the first token halfway through
        self.given_target()
        self.publisher.upload_failures = [rejected({"offset": 512})]

        # When: the worker runs it
        status = self.pipeline.run(1)

        # Then: the second attempt used a fresh token and the saved resume point
        self.assertEqual(status, TargetStatus.COMPLETED)
        self.assertEqual(self.publisher.tokens_seen, ["stale", "fresh"])
        self.assertEqual(self.publisher.resumed_from[1], {"offset": 512})

    def test_a_platform_that_confirms_later_gets_its_first_poll_scheduled(self):
        # Given: a platform that processes the video after the upload
        row = self.given_target()
        self.publisher.published = Published.awaiting_confirmation()

        # When: the worker runs it
        status = self.pipeline.run(1)

        # Then: it waits, knows since when, and the first poll is queued
        self.assertEqual(status, TargetStatus.PROCESSING)
        self.assertEqual(row.job.resume_state, {"confirming_since": self.clock.now().isoformat(), "polls": 0})
        self.assertEqual(self.queue.confirmations, [(1, ConfirmationPoller.POLL_DELAYS_SECONDS[0])])


class ConfirmationScenarios(ScenarioBase):
    def test_a_platform_still_working_is_asked_again_later(self):
        # Given: a target waiting for the platform
        row = self.given_processing()
        self.publisher.confirmations = [NotReady()]

        # When: it is polled
        delay = self.poller.confirm(1)

        # Then: the next poll is further out and the count went up
        self.assertEqual(delay, ConfirmationPoller.POLL_DELAYS_SECONDS[1])
        self.assertEqual(row.job.resume_state["polls"], 1)
        self.assertEqual(self.queue.confirmations, [(1, delay)])

    def test_a_platform_silent_past_the_window_fails_the_target(self):
        # Given: a target waiting longer than the confirmation window
        row = self.given_processing()
        self.clock.advance(timedelta(seconds=ConfirmationPoller.CONFIRM_WITHIN_SECONDS + 1))

        # When: it is polled once more
        delay = self.poller.confirm(1)

        # Then: it stops asking and fails
        self.assertIsNone(delay)
        self.assertEqual(row.status, TargetStatus.FAILED)
        self.assertEqual(row.fields["error"]["type"], FailureType.PLATFORM)

    def test_a_window_start_stored_as_a_timestamp_is_still_understood(self):
        # Given: a target that started confirming before the times were stored as text
        row = self.given_processing()
        row.job = row.job.resumed_from({"confirming_since": self.clock.now().timestamp(), "polls": 3})
        self.clock.advance(timedelta(seconds=ConfirmationPoller.CONFIRM_WITHIN_SECONDS + 1))

        # When / Then: its window has run out as well
        self.assertIsNone(self.poller.confirm(1))
        self.assertEqual(row.status, TargetStatus.FAILED)

    def test_a_ready_commit_is_marked_before_it_is_sent(self):
        # Given: the platform is ready and the final step cannot be repeated safely
        row = self.given_processing()
        self.publisher.confirmations = [ReadyToCommit()]

        # When: it is polled
        self.poller.confirm(1)

        # Then: the mark was written before the commit, and the post is completed
        marked = [entry["resume_state"] for entry in self.targets.history if "resume_state" in entry]
        self.assertIn(COMMIT_STARTED, marked[0])
        self.assertEqual(row.status, TargetStatus.COMPLETED)
        self.assertEqual(row.fields["published_url"], "https://fake.test/post")

    def test_an_unanswered_commit_keeps_the_mark_and_warns(self):
        # Given: the commit went out but no answer came back
        row = self.given_processing()
        self.publisher.confirmations = [ReadyToCommit()]
        self.publisher.commit_outcome = PlatformError(FailureType.NETWORK, "timed out", retryable=True)

        # When: it is polled
        self.poller.confirm(1)

        # Then: the target fails as possibly posted and the mark stays
        self.assertEqual(row.status, TargetStatus.FAILED)
        self.assertIn("may have been created", row.fields["error"]["message"])
        self.assertIn(COMMIT_STARTED, row.job.resume_state)

    def test_a_refused_commit_clears_the_mark(self):
        # Given: the platform clearly refused the commit
        row = self.given_processing()
        self.publisher.confirmations = [ReadyToCommit()]
        self.publisher.commit_outcome = PlatformError(FailureType.VALIDATION, "Text too long")

        # When: it is polled
        self.poller.confirm(1)

        # Then: nothing was posted, so a retry may commit again
        self.assertEqual(row.fields["error"]["type"], FailureType.VALIDATION)
        self.assertNotIn(COMMIT_STARTED, row.job.resume_state)

    def test_a_commit_already_started_is_not_sent_twice(self):
        # Given: an earlier commit may have gone out
        row = self.given_processing(**{COMMIT_STARTED: self.clock.now().isoformat()})
        self.publisher.confirmations = [ReadyToCommit()]

        # When: it is polled again
        self.poller.confirm(1)

        # Then: it refuses to guess
        self.assertEqual(row.status, TargetStatus.FAILED)
        self.assertIn("may have been created", row.fields["error"]["message"])

    def test_a_platform_that_can_tell_resolves_the_uncertain_commit(self):
        # Given: an earlier commit may have gone out, and the platform can say it did
        row = self.given_processing(**{COMMIT_STARTED: self.clock.now().isoformat()})
        self.publisher.uncertain = Published(TargetStatus.COMPLETED, "https://fake.test/found")

        # When: it is polled again
        self.poller.confirm(1)

        # Then: the found post completes the target
        self.assertEqual(row.status, TargetStatus.COMPLETED)
        self.assertEqual(row.fields["published_url"], "https://fake.test/found")
