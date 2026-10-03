from unittest import mock

from asgiref.sync import sync_to_async
from django.utils import timezone

from media import storage
from platforms2.core import PlatformError, PlatformFailure
from platforms2.core.usecases.accounts import TokenService
from platforms2.core.usecases.publications import StaleTargetSweeper
from publishing import tasks
from publishing.models import PublicationTarget
from publishing.repositories import DjangoTargetRepository

from .base import CHUNK, CONTENT, VIDEO_ID, PublishingTestCase

Status = PublicationTarget.Status


class UploadScenarios(PublishingTestCase):
    def given_target(self, **overrides) -> PublicationTarget:
        self.create_publication(**overrides)
        return self.only_target()

    def test_a_video_is_sent_in_chunks_and_published(self):
        # Given: a queued target and a platform that accepts everything
        target = self.given_target()
        google = self.given_google()

        # When: the worker runs it
        result = self.run_target(target.pk)

        # Then: the whole file arrived, in pieces, and the video is live
        self.assertEqual(result, Status.COMPLETED)
        self.assertEqual(b"".join(google.chunks), CONTENT)
        self.assertEqual(len(google.chunks), len(CONTENT) // CHUNK)
        target.refresh_from_db()
        self.assertEqual(target.uploaded_media_id, VIDEO_ID)
        self.assertEqual(target.published_url, f"https://youtu.be/{VIDEO_ID}")
        self.assertEqual(target.progress, 100)
        self.assertEqual(google.tokens[0], "ya29.token")

    def test_the_content_range_header_describes_each_piece(self):
        target = self.given_target()
        google = self.given_google()

        self.run_target(target.pk)

        self.assertEqual(google.ranges[0], f"bytes 0-{CHUNK - 1}/{len(CONTENT)}")
        self.assertEqual(
            google.ranges[-1], f"bytes {len(CONTENT) - CHUNK}-{len(CONTENT) - 1}/{len(CONTENT)}"
        )

    def test_progress_is_recorded_while_the_upload_runs(self):
        # Given: a target whose progress is watched as it goes
        target = self.given_target()
        self.given_google()
        seen: list[int] = []

        @sync_to_async
        def spy(repository, target_id, **fields):
            if "progress" in fields:
                seen.append(fields["progress"])
            PublicationTarget.objects.filter(pk=target_id).update(**fields)

        with mock.patch.object(DjangoTargetRepository, "update", spy):
            self.run_target(target.pk)

        # Then: the bar moved on whole percents up to the end
        self.assertEqual(seen[0], 0)
        self.assertEqual(seen[-1], 100)
        self.assertEqual(seen, sorted(seen))

    def test_a_transient_failure_is_retried(self):
        # Given: the platform fails once in the middle with a 500
        target = self.given_target()
        google = self.given_google(fail_at=CHUNK * 2)

        result = self.run_target(target.pk)

        self.assertEqual(result, Status.COMPLETED)
        self.assertEqual(b"".join(google.chunks), CONTENT)

    def test_a_rejected_upload_is_not_retried(self):
        # Given: the platform rejects the file outright
        target = self.given_target()
        google = self.given_google(fail_at=0, failure=(400, {"error": {"code": 400, "message": "bad file"}}))

        result = self.run_target(target.pk)

        # Then: it fails with the platform's words. Repeating it would burn quota
        # for a file the platform has already decided about.
        self.assertEqual(result, Status.FAILED)
        target.refresh_from_db()
        self.assertEqual(target.error["failure"], PlatformFailure.REFUSED)
        self.assertIn("bad file", target.error["message"])
        self.assertEqual(len(google.ranges), 1)

    def test_an_expired_token_is_refreshed_and_the_upload_starts_again(self):
        # Given: Google answers 401 partway through
        target = self.given_target()
        google = self.given_google(fail_at=CHUNK * 2, failure=(401, {"error": {"code": 401, "message": "expired"}}))

        # When: the upload runs with a token our clock still thinks is good
        with (
            mock.patch.object(TokenService, "valid", new=mock.AsyncMock(return_value="stale-token")),
            mock.patch.object(TokenService, "refresh", new=mock.AsyncMock(return_value="fresh-token")) as refresh,
        ):
            result = self.run_target(target.pk)

        # Then: the token was refreshed for real, and a new upload carried the whole file
        self.assertEqual(result, Status.COMPLETED)
        refresh.assert_awaited_once()
        self.assertEqual(google.tokens[:2], ["stale-token", "fresh-token"])
        self.assertEqual(google.session_calls, 2)
        self.assertEqual(google.received, len(CONTENT))

    def test_a_missing_file_fails_before_anything_is_sent(self):
        target = self.given_target()
        storage.absolute(self.asset.storage_path).unlink()
        google = self.given_google()

        result = self.run_target(target.pk)

        self.assertEqual(result, Status.FAILED)
        target.refresh_from_db()
        self.assertEqual(target.error["failure"], PlatformFailure.MEDIA_MISSING)
        self.assertEqual(google.session_calls, 0)

    def test_a_video_without_a_title_is_refused_by_validation(self):
        target = self.given_target()
        target.publication.title = "   "
        target.publication.save()
        self.given_google()

        result = self.run_target(target.pk)

        self.assertEqual(result, Status.FAILED)
        target.refresh_from_db()
        self.assertEqual(target.error["failure"], PlatformFailure.INVALID)
        self.assertIn("titleRequired", target.error["details"])

    def test_a_target_already_taken_is_left_alone(self):
        # Given: a target somebody else is already running
        target = self.given_target()
        PublicationTarget.objects.filter(pk=target.pk).update(
            status=Status.UPLOADING, last_activity_at=timezone.now()
        )

        result = self.run_target(target.pk)

        self.assertIsNone(result)

    def test_a_target_whose_worker_died_is_failed_and_asks_to_publish_again(self):
        # Given: a target stuck uploading, untouched for longer than a worker would be
        target = self.given_target()
        PublicationTarget.objects.filter(pk=target.pk).update(
            status=Status.UPLOADING,
            last_activity_at=timezone.now() - StaleTargetSweeper.ABANDONED_AFTER * 2,
        )

        # When: the task is delivered again, and the sweep runs
        self.assertIsNone(self.run_target(target.pk))
        swept = tasks.sweep_abandoned_targets()

        # Then: it failed with a reason the person can act on
        self.assertEqual(swept, 1)
        target.refresh_from_db()
        self.assertEqual(target.status, Status.FAILED)
        self.assertIn("publish again", target.error["message"])
        self.assertIsNotNone(target.finished_at)

    def test_a_passing_refresh_failure_is_reported_as_a_network_problem(self):
        # Given: the token cannot be refreshed because Google is unreachable
        target = self.given_target()
        unreachable = PlatformError(PlatformFailure.NETWORK, "YouTube request failed: ClientConnectionError")
        with mock.patch.object(TokenService, "valid", new=mock.AsyncMock(side_effect=unreachable)):
            # When: the target runs
            result = self.run_target(target.pk)

        # Then: it fails as network, so the person is not told to reconnect
        self.assertEqual(result, Status.FAILED)
        target.refresh_from_db()
        self.assertEqual(target.error["failure"], PlatformFailure.NETWORK)

    def test_a_cancelled_target_stops_before_the_upload(self):
        target = self.given_target()
        google = self.given_google()
        PublicationTarget.objects.filter(pk=target.pk).update(cancel_requested=True)

        result = self.run_target(target.pk)

        self.assertEqual(result, Status.CANCELLED)
        self.assertEqual(google.session_calls, 0)

    def test_a_retry_after_the_bytes_landed_uploads_from_the_start(self):
        # Given: a target that uploaded but failed while publishing, and was retried
        target = self.given_target()
        PublicationTarget.objects.filter(pk=target.pk).update(status=Status.FAILED, uploaded_media_id=VIDEO_ID)
        self.client.post(f"/api/targets/{target.pk}/retry")
        google = self.given_google()

        # When: the worker runs it
        result = self.run_target(target.pk)

        # Then: the whole file went up again in a new upload
        self.assertEqual(result, Status.COMPLETED)
        self.assertEqual(b"".join(google.chunks), CONTENT)
