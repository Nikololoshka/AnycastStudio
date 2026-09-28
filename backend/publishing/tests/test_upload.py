from unittest import mock

from django.utils import timezone

from media import storage
from publishing import pipeline
from publishing.models import PublicationTarget

from platforms.core.errors import ProviderError
from .base import CHUNK, CONTENT, SESSION_URI, VIDEO_ID, FakeResponse, PublishingTestCase

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
        result = pipeline.run_target(target.pk)

        # Then: the whole file arrived, in pieces, and the video is live
        self.assertEqual(result, Status.COMPLETED)
        self.assertEqual(b"".join(google.chunks), CONTENT)
        target.refresh_from_db()
        self.assertEqual(target.uploaded_media_id, VIDEO_ID)
        self.assertEqual(target.published_url, f"https://youtu.be/{VIDEO_ID}")
        self.assertEqual(target.progress, 100)

    def test_the_content_range_header_describes_each_piece(self):
        target = self.given_target()
        google = self.given_google()

        pipeline.run_target(target.pk)

        self.assertEqual(google.ranges[0], f"bytes 0-{CHUNK - 1}/{len(CONTENT)}")
        self.assertEqual(
            google.ranges[-1], f"bytes {len(CONTENT) - CHUNK}-{len(CONTENT) - 1}/{len(CONTENT)}"
        )

    def test_the_resume_point_is_recorded_while_the_upload_runs(self):
        # Given: a target whose progress is watched as it goes
        target = self.given_target()
        self.given_google()
        seen: list[dict] = []
        original = pipeline._set

        def spy(row, **fields):
            if "resume_state" in fields and fields["resume_state"]:
                seen.append(fields["resume_state"])
            original(row, **fields)

        with mock.patch.object(pipeline, "_set", spy):
            pipeline.run_target(target.pk)

        # Then: every chunk left a point a restarted worker could continue from
        self.assertTrue(seen)
        self.assertEqual(seen[0]["session_uri"], SESSION_URI)
        self.assertEqual(seen[-1]["offset"], len(CONTENT))

    def test_a_restarted_worker_continues_instead_of_sending_the_file_again(self):
        # Given: a target that already sent half the file before dying
        target = self.given_target()
        half = len(CONTENT) // 2
        PublicationTarget.objects.filter(pk=target.pk).update(
            status=Status.QUEUED,
            resume_state={"session_uri": SESSION_URI, "offset": half},
        )
        google = self.given_google()
        google.received = half

        pipeline.run_target(target.pk)

        # Then: only the remainder went, and no new session was opened
        self.assertEqual(b"".join(google.chunks), CONTENT[half:])
        self.assertEqual(google.session_calls, 0)

    def test_googles_offset_wins_over_our_arithmetic(self):
        # Given: a platform that confirms less than we sent, which is what a
        # partially written chunk looks like
        target = self.given_target()
        google = self.given_google()
        real_call = google.__call__

        def short_confirm(method, url, **kwargs):
            response = real_call(method, url, **kwargs)
            if url == SESSION_URI and response.status_code == 308:
                google.received -= 1
                response.headers["Range"] = f"bytes=0-{google.received - 1}"
            return response

        self.http.side_effect = short_confirm

        pipeline.run_target(target.pk)

        target.refresh_from_db()
        self.assertEqual(target.status, Status.COMPLETED)

    def test_a_transient_failure_is_retried(self):
        # Given: the platform fails once in the middle with a 500
        target = self.given_target()
        google = self.given_google(fail_at=CHUNK * 2)

        result = pipeline.run_target(target.pk)

        self.assertEqual(result, Status.COMPLETED)
        self.assertEqual(b"".join(google.chunks), CONTENT)

    def test_a_rejected_upload_is_not_retried(self):
        # Given: the platform rejects the file outright
        target = self.given_target()
        self.given_google(
            fail_at=0, failure=FakeResponse(400, {"error": {"message": "bad file"}})
        )

        result = pipeline.run_target(target.pk)

        # Then: it fails as a validation error. Repeating it would burn quota
        # for a file the platform has already decided about.
        self.assertEqual(result, Status.FAILED)
        target.refresh_from_db()
        self.assertEqual(target.error["type"], "validation")

    def test_an_expired_token_is_refreshed_and_the_upload_continues(self):
        # Given: Google answers 401 partway through
        target = self.given_target()
        google = self.given_google(
            fail_at=CHUNK * 2, failure=FakeResponse(401, {"error": {"message": "expired"}})
        )

        # When: the upload runs with a token our clock still thinks is good
        with (
            mock.patch(
                "publishing.pipeline.social_services.get_valid_access_token", return_value="stale-token"
            ),
            mock.patch(
                "publishing.pipeline.social_services.refresh_access_token", return_value="fresh-token"
            ) as refresh,
        ):
            result = pipeline.run_target(target.pk)

        # Then: the token was refreshed for real, not re-read, and the rest of the file went up
        self.assertEqual(result, Status.COMPLETED)
        refresh.assert_called_once()
        self.assertEqual(b"".join(google.chunks), CONTENT)

    def test_a_missing_file_fails_before_anything_is_sent(self):
        target = self.given_target()
        storage.absolute(self.asset.storage_path).unlink()
        self.given_google()

        result = pipeline.run_target(target.pk)

        self.assertEqual(result, Status.FAILED)
        target.refresh_from_db()
        self.assertEqual(target.error["type"], "file")

    def test_a_video_without_a_title_is_refused_by_validation(self):
        target = self.given_target()
        target.publication.title = "   "
        target.publication.save()
        self.given_google()

        result = pipeline.run_target(target.pk)

        self.assertEqual(result, Status.FAILED)
        target.refresh_from_db()
        self.assertEqual(target.error["type"], "validation")
        self.assertIn("titleRequired", target.error["details"])

    def test_a_target_already_taken_is_left_alone(self):
        # Given: a target somebody else is already running
        target = self.given_target()
        PublicationTarget.objects.filter(pk=target.pk).update(
            status=Status.UPLOADING, last_activity_at=timezone.now()
        )

        result = pipeline.run_target(target.pk)

        self.assertEqual(result, "")

    def test_a_target_whose_worker_died_is_taken_over_and_resumed(self):
        # Given: a target stuck uploading halfway, untouched for longer than a worker would be
        target = self.given_target()
        half = len(CONTENT) // 2
        PublicationTarget.objects.filter(pk=target.pk).update(
            status=Status.UPLOADING,
            last_activity_at=timezone.now() - pipeline.ABANDONED_AFTER * 2,
            resume_state={"session_uri": SESSION_URI, "offset": half},
        )
        google = self.given_google()
        google.received = half

        # When: the task is delivered again
        result = pipeline.run_target(target.pk)

        # Then: it finishes, sending only what Google did not have
        self.assertEqual(result, Status.COMPLETED)
        self.assertEqual(b"".join(google.chunks), CONTENT[half:])

    def test_a_passing_refresh_failure_is_reported_as_a_network_problem(self):
        # Given: the token cannot be refreshed because Google is unreachable
        target = self.given_target()
        with mock.patch(
            "publishing.pipeline.social_services.get_valid_access_token",
            side_effect=ProviderError("Google request failed: ConnectionError", transient=True),
        ):
            # When: the target runs
            result = pipeline.run_target(target.pk)

        # Then: it fails as network, so the person is not told to reconnect
        self.assertEqual(result, Status.FAILED)
        target.refresh_from_db()
        self.assertEqual(target.error["type"], "network")

    def test_a_cancelled_target_stops_between_chunks(self):
        target = self.given_target()
        self.given_google()
        PublicationTarget.objects.filter(pk=target.pk).update(cancel_requested=True)

        result = pipeline.run_target(target.pk)

        self.assertEqual(result, Status.CANCELLED)

    def test_a_retry_after_the_bytes_landed_does_not_upload_again(self):
        # Given: a target that uploaded but failed while publishing
        target = self.given_target()
        PublicationTarget.objects.filter(pk=target.pk).update(
            status=Status.QUEUED, uploaded_media_id=VIDEO_ID
        )
        google = self.given_google()

        result = pipeline.run_target(target.pk)

        self.assertEqual(result, Status.COMPLETED)
        self.assertEqual(google.chunks, [])
