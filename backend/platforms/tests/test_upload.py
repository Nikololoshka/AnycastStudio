from platforms.http import PlatformFailure
from platforms.youtube import ResumeState, VideoMetadata, upload

from .base import CHUNK, CONTENT, SESSION_URI, VIDEO_ID, FakeResponse, PlatformTestCase, persisted

METADATA = VideoMetadata(
    title="A clip",
    description="",
    tags=[],
    privacy_status="private",
    category_id="22",
    license="youtube",
    embeddable=True,
    public_stats_viewable=True,
    made_for_kids=False,
    contains_synthetic_media=False,
    notify_subscribers=True,
)


class ResumeScenarios(PlatformTestCase):
    def resume(self, offset: int):
        return upload(
            path=self.given_file(),
            size=len(CONTENT),
            mime_type="video/mp4",
            metadata=METADATA,
            access_token="ya29.token",
            resume=ResumeState(session_uri=SESSION_URI, offset=offset),
        )

    def test_a_resumed_upload_asks_google_where_to_continue(self):
        # Given: our record says 1024 bytes, but Google already has 3072
        self.http.side_effect = [
            persisted(3 * CHUNK),
            persisted(4 * CHUNK),
            FakeResponse(200, {"id": VIDEO_ID}),
        ]

        # When: the upload resumes
        video_id = self.resume(offset=CHUNK)

        # Then: it asked first, and sent only what Google did not have
        self.assertEqual(video_id, VIDEO_ID)
        self.assertEqual(
            self.sent_ranges(),
            [f"bytes */{len(CONTENT)}", f"bytes 3072-4095/{len(CONTENT)}", f"bytes 4096-5119/{len(CONTENT)}"],
        )

    def test_a_resumed_upload_that_google_already_finished_sends_nothing(self):
        # Given: the worker died after the last chunk, before reading the id
        self.http.side_effect = [FakeResponse(200, {"id": VIDEO_ID})]

        # When: it resumes at the very end of the file
        video_id = self.resume(offset=len(CONTENT))

        # Then: the id comes from the progress query alone
        self.assertEqual(video_id, VIDEO_ID)
        self.assertEqual(self.http.call_count, 1)


class OffsetScenarios(PlatformTestCase):
    def upload_fresh(self):
        return upload(
            path=self.given_file(),
            size=len(CONTENT),
            mime_type="video/mp4",
            metadata=METADATA,
            access_token="ya29.token",
        )

    def test_a_308_without_a_range_means_nothing_was_kept(self):
        # Given: Google answers the first chunk without a Range header
        session = FakeResponse(200, headers={"Location": SESSION_URI})
        chunks = [persisted(0)] + [persisted(n * CHUNK) for n in range(1, 5)] + [FakeResponse(200, {"id": VIDEO_ID})]
        self.http.side_effect = [session, *chunks]

        # When: the file is uploaded
        self.upload_fresh()

        # Then: the first chunk is sent again from byte zero
        ranges = self.sent_ranges()
        self.assertEqual(ranges[0], ranges[1])
        self.assertTrue(ranges[1].startswith("bytes 0-"))

    def test_an_upload_that_never_advances_gives_up(self):
        # Given: Google keeps nothing, however often the chunk is sent
        session = FakeResponse(200, headers={"Location": SESSION_URI})
        self.http.side_effect = [session] + [persisted(0)] * 10

        # When / Then: it stops instead of looping forever
        with self.assertRaises(PlatformFailure):
            self.upload_fresh()
        self.assertEqual(self.http.call_count, 1 + 3)
