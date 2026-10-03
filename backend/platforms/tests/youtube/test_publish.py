import json
from datetime import UTC, datetime
from unittest import mock

from googleapiclient.discovery import build
from googleapiclient.http import HttpMockSequence

from platforms.core import PlatformError, PlatformFailure, Published, Scheduled
from platforms.youtube import YouTubeConfig
from platforms.youtube.publish import YouTubePublishInteractor
from platforms.youtube.publish.youtube_api import YouTubeApi

from ..base import CHUNK, CONTENT, REDIRECT, PlatformTestCase

CONFIG = YouTubeConfig("client-id", "client-secret", REDIRECT.format(platform="youtube"), chunk_bytes=CHUNK, retries=0)
SESSION_URI = "https://upload.googleapis.com/session/abc"
VIDEO_ID = "vid_abc123"


def started() -> tuple[dict, str]:
    return {"status": "200", "location": SESSION_URI}, ""


def kept(received: int) -> tuple[dict, str]:
    return {"status": "308", "range": f"bytes=0-{received - 1}"}, ""


def finished(body: dict | None = None) -> tuple[dict, str]:
    return {"status": "200"}, json.dumps({"id": VIDEO_ID} if body is None else body)


def refused(status: int, reason: str) -> tuple[dict, str]:
    return {"status": str(status)}, json.dumps({"error": {"code": status, "message": reason, "errors": [{"reason": reason}]}})


class YouTubePublishTestCase(PlatformTestCase):
    def given_google(self, *exchanges) -> HttpMockSequence:
        google = HttpMockSequence(list(exchanges))
        videos = build("youtube", "v3", http=google, static_discovery=True, cache_discovery=False).videos()
        patcher = mock.patch.object(YouTubeApi, "videos", return_value=videos)
        self.videos = patcher.start()
        self.addCleanup(patcher.stop)
        return google


class YouTubeUploadScenarios(YouTubePublishTestCase):
    async def test_the_video_goes_in_chunks_and_ends_with_its_id(self):
        # Given: Google keeps every chunk and finishes with the video id
        google = self.given_google(started(), kept(1024), kept(2048), kept(3072), kept(4096), finished())

        # When: the video is uploaded
        events = await self.drain(YouTubePublishInteractor(CONFIG).upload(self.given_job(), "ya29.token"))

        # Then: progress follows the bytes Google kept, and the last event carries the video id
        self.assertEqual([event.uploaded_bytes for event in events], [1024, 2048, 3072, 4096, len(CONTENT)])
        self.assertEqual(events[-1].media_id, VIDEO_ID)
        self.assertEqual(len(google.request_sequence), 6)
        self.videos.assert_called_with("ya29.token")

    async def test_the_metadata_carries_the_draft_and_the_options(self):
        # Given: a draft with hashtags and chosen options
        google = self.given_google(started(), finished())
        job = self.given_job(
            self.given_file(b"x" * 100),
            title="Title",
            description="Body",
            hashtags=("a", "b"),
            settings={"privacyStatus": "unlisted", "categoryId": "10", "madeForKids": True},
        )

        # When: the upload starts
        await self.drain(YouTubePublishInteractor(CONFIG).upload(job, "ya29.token"))

        # Then: the insert body is the metadata of the draft
        uri, _, body, _ = google.request_sequence[0]
        metadata = json.loads(body)
        self.assertIn("uploadType=resumable", uri)
        self.assertEqual(metadata["snippet"]["title"], "Title")
        self.assertEqual(metadata["snippet"]["description"], "Body\n\n#a #b")
        self.assertEqual(metadata["snippet"]["tags"], ["a", "b"])
        self.assertEqual(metadata["snippet"]["categoryId"], "10")
        self.assertEqual(metadata["status"]["privacyStatus"], "unlisted")
        self.assertTrue(metadata["status"]["selfDeclaredMadeForKids"])

    async def test_a_scheduled_video_is_uploaded_private(self):
        google = self.given_google(started(), finished())
        job = self.given_job(
            self.given_file(b"x" * 100),
            settings={"privacyStatus": "public"},
            publish_at=datetime(2030, 1, 1, tzinfo=UTC),
        )

        await self.drain(YouTubePublishInteractor(CONFIG).upload(job, "ya29.token"))

        self.assertEqual(json.loads(google.request_sequence[0][2])["status"]["privacyStatus"], "private")

    async def test_an_exhausted_quota_is_a_limit(self):
        # Given: Google refuses the upload because the daily quota is spent
        self.given_google(refused(403, "quotaExceeded"))

        # When / Then: the failure is a rate limit with Google's words
        with self.assertRaises(PlatformError) as raised:
            await self.drain(YouTubePublishInteractor(CONFIG).upload(self.given_job(), "ya29.token"))
        self.assertEqual(raised.exception.failure, PlatformFailure.RATE_LIMITED)
        self.assertIn("quotaExceeded", raised.exception.message)

    async def test_a_rejected_token_asks_for_a_fresh_one(self):
        self.given_google(({"status": "401"}, json.dumps({"error": {"code": 401, "message": "Invalid Credentials"}})))

        with self.assertRaises(PlatformError) as raised:
            await self.drain(YouTubePublishInteractor(CONFIG).upload(self.given_job(), "ya29.token"))

        self.assertEqual(raised.exception.failure, PlatformFailure.TOKEN_REJECTED)

    async def test_a_deleted_file_is_media_missing(self):
        # Given: the file disappeared after the job was made
        path = self.given_file()
        job = self.given_job(path)
        path.unlink()
        self.given_google(started())

        # When / Then: the upload stops as media missing
        with self.assertRaises(PlatformError) as raised:
            await self.drain(YouTubePublishInteractor(CONFIG).upload(job, "ya29.token"))
        self.assertEqual(raised.exception.failure, PlatformFailure.MEDIA_MISSING)

    async def test_an_answer_without_an_id_is_unexpected(self):
        self.given_google(started(), finished({}))

        with self.assertRaises(PlatformError) as raised:
            await self.drain(YouTubePublishInteractor(CONFIG).upload(self.given_job(self.given_file(b"x" * 100)), "t"))

        self.assertEqual(raised.exception.failure, PlatformFailure.UNEXPECTED)


class YouTubeVisibilityScenarios(YouTubePublishTestCase):
    async def test_a_video_is_published_with_the_chosen_privacy(self):
        # Given: an uploaded video
        google = self.given_google(({"status": "200"}, json.dumps({"id": VIDEO_ID})))
        job = self.given_job(media_id=VIDEO_ID, settings={"privacyStatus": "public"})

        # When: it is published
        outcome = await YouTubePublishInteractor(CONFIG).publish(job, "ya29.token")

        # Then: the status update made it public, and the link points at it
        self.assertEqual(outcome, Published(f"https://youtu.be/{VIDEO_ID}"))
        body = json.loads(google.request_sequence[0][2])
        self.assertEqual(body["id"], VIDEO_ID)
        self.assertEqual(body["status"]["privacyStatus"], "public")

    async def test_a_scheduled_video_is_left_to_google_to_publish(self):
        google = self.given_google(({"status": "200"}, json.dumps({"id": VIDEO_ID})))
        publish_at = datetime(2030, 1, 1, 12, tzinfo=UTC)
        job = self.given_job(media_id=VIDEO_ID, settings={"privacyStatus": "public"}, publish_at=publish_at)

        outcome = await YouTubePublishInteractor(CONFIG).publish(job, "ya29.token")

        self.assertEqual(outcome, Scheduled(f"https://youtu.be/{VIDEO_ID}"))
        status = json.loads(google.request_sequence[0][2])["status"]
        self.assertEqual(status["privacyStatus"], "private")
        self.assertEqual(status["publishAt"], publish_at.isoformat())

    async def test_a_wrong_publish_time_is_invalid(self):
        self.given_google(refused(400, "invalidPublishAt"))
        job = self.given_job(media_id=VIDEO_ID, publish_at=datetime(2000, 1, 1, tzinfo=UTC))

        with self.assertRaises(PlatformError) as raised:
            await YouTubePublishInteractor(CONFIG).publish(job, "ya29.token")

        self.assertEqual(raised.exception.failure, PlatformFailure.INVALID)
