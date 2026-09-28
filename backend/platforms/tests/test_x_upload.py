import time

from platforms.core.errors import FailureType, PlatformError
from platforms.upload import NeedsFreshToken, UploadCancelled
from platforms.x import ResumeState, upload
from platforms.x.client import API_ROOT

from .base import CHUNK, CONTENT, FakeResponse, PlatformTestCase

MEDIA_ID = "1880000000000000001"
NEW_MEDIA_ID = "1880000000000000002"
TOKEN = "x.access-token"

INITIALIZE = f"{API_ROOT}/media/upload/initialize"
MEDIA_ROOT = f"{API_ROOT}/media/upload/"


class XDouble:
    def __init__(self, media_ids=None):
        self.media_ids = list(media_ids or [MEDIA_ID])
        self.initialized: list[dict] = []
        self.received: list[tuple[str, int, bytes]] = []
        self.finalized: list[str] = []
        self.append_failure = None

    def __call__(self, method, url, **kwargs):
        if kwargs["headers"].get("Authorization") != f"Bearer {TOKEN}":
            raise AssertionError(f"unexpected headers {kwargs['headers']}")
        if url == INITIALIZE:
            self.initialized.append(kwargs["json"])
            return FakeResponse(200, {"data": {"id": self.media_ids.pop(0), "expires_after_secs": 86400}})
        if url.startswith(MEDIA_ROOT) and url.endswith("/append"):
            if self.append_failure is not None:
                failure, self.append_failure = self.append_failure, None
                return failure
            _, piece, _ = kwargs["files"]["media"]
            self.received.append((url.split("/")[-2], int(kwargs["data"]["segment_index"]), piece))
            return FakeResponse(200, {})
        if url.startswith(MEDIA_ROOT) and url.endswith("/finalize"):
            self.finalized.append(url.split("/")[-2])
            return FakeResponse(200, {"data": {"id": MEDIA_ID, "processing_info": {"state": "pending"}}})
        raise AssertionError(f"unexpected call to {method} {url}")

    def bytes_received(self) -> bytes:
        return b"".join(piece for _, _, piece in self.received)


class XUploadScenarios(PlatformTestCase):
    def send(self, **kwargs):
        defaults = {"path": self.given_file(), "size": len(CONTENT), "mime_type": "video/mp4", "access_token": TOKEN}
        return upload(**{**defaults, **kwargs})

    def resume_state(self, next_segment: int, age_seconds: float = 60) -> ResumeState:
        return ResumeState(
            media_id=MEDIA_ID, segment_bytes=CHUNK, next_segment=next_segment, created_at=time.time() - age_seconds
        )

    def test_the_upload_announces_the_whole_video_as_a_post_video(self):
        # Given: X accepts everything
        double = XDouble()
        self.http.side_effect = double

        # When: the video is uploaded
        media_id = self.send()

        # Then: one upload was opened for the whole file, and it was finalized
        self.assertEqual(media_id, MEDIA_ID)
        self.assertEqual(
            double.initialized,
            [{"media_type": "video/mp4", "total_bytes": len(CONTENT), "media_category": "tweet_video"}],
        )
        self.assertEqual(double.finalized, [MEDIA_ID])

    def test_every_byte_goes_once_and_in_order(self):
        double = XDouble()
        self.http.side_effect = double

        self.send()

        self.assertEqual(double.bytes_received(), CONTENT)
        self.assertEqual([index for _, index, _ in double.received], list(range(len(CONTENT) // CHUNK)))

    def test_a_last_segment_shorter_than_the_rest_is_sent_whole(self):
        # Given: a file that does not end on a segment boundary
        content = CONTENT + b"tail"
        double = XDouble()
        self.http.side_effect = double

        # When: it is uploaded
        self.send(path=self.given_file(content), size=len(content))

        # Then: the last segment carries exactly the remainder
        self.assertEqual(double.received[-1][2], b"tail")
        self.assertEqual(double.bytes_received(), content)

    def test_progress_reports_the_bytes_accepted(self):
        self.http.side_effect = XDouble()
        reports = []

        self.send(on_progress=lambda uploaded, total, state: reports.append(uploaded))

        self.assertEqual(reports[0], CHUNK)
        self.assertEqual(reports[-1], len(CONTENT))

    def test_a_resumed_upload_continues_from_the_next_segment(self):
        # Given: a worker died after two segments
        double = XDouble()
        self.http.side_effect = double

        # When: the upload resumes
        media_id = self.send(resume=self.resume_state(next_segment=2))

        # Then: no new upload, and only the rest of the file
        self.assertEqual(media_id, MEDIA_ID)
        self.assertEqual(double.initialized, [])
        self.assertEqual(double.bytes_received(), CONTENT[2 * CHUNK :])
        self.assertEqual(double.received[0][1], 2)

    def test_an_upload_older_than_the_media_lifetime_starts_again(self):
        # Given: an unfinished upload from yesterday
        double = XDouble(media_ids=[NEW_MEDIA_ID])
        self.http.side_effect = double

        # When: the upload resumes
        media_id = self.send(resume=self.resume_state(next_segment=2, age_seconds=24 * 60 * 60))

        # Then: a new upload carries the whole file
        self.assertEqual(media_id, NEW_MEDIA_ID)
        self.assertEqual(len(double.initialized), 1)
        self.assertEqual(double.bytes_received(), CONTENT)

    def test_a_rejected_token_mid_upload_keeps_the_position(self):
        # Given: the token expires after the first segment
        double = XDouble()
        self.http.side_effect = double

        def expire_after_first(uploaded, total, state):
            double.append_failure = FakeResponse(401, {"title": "Unauthorized", "type": "about:blank"})

        # When / Then: the upload stops asking for a fresh token, holding the next segment
        with self.assertRaises(NeedsFreshToken) as raised:
            self.send(on_progress=expire_after_first)
        self.assertEqual(raised.exception.state["media_id"], MEDIA_ID)
        self.assertEqual(raised.exception.state["next_segment"], 1)

    def test_a_cancel_stops_before_the_next_segment(self):
        double = XDouble()
        self.http.side_effect = double
        asked = []

        def cancel_after_two():
            asked.append(True)
            return len(asked) > 2

        with self.assertRaises(UploadCancelled) as raised:
            self.send(should_cancel=cancel_after_two)
        self.assertEqual(raised.exception.state["next_segment"], 2)
        self.assertEqual(double.finalized, [])

    def test_a_refused_file_is_not_retried(self):
        # Given: X refuses the file type
        refusal = {
            "title": "Invalid Request",
            "detail": "Unsupported media type",
            "type": "https://api.x.com/2/problems/invalid-request",
        }
        self.http.side_effect = [FakeResponse(400, refusal)]

        # When / Then: the refusal carries X's kind and detail, and it was asked once
        with self.assertRaises(PlatformError) as raised:
            self.send()
        self.assertEqual(raised.exception.type, FailureType.VALIDATION)
        self.assertEqual(raised.exception.details, "invalid-request")
        self.assertEqual(raised.exception.message, "Unsupported media type")
        self.assertEqual(self.http.call_count, 1)

    def test_an_expired_token_at_the_start_asks_for_a_fresh_one(self):
        self.http.side_effect = [FakeResponse(401, {"title": "Unauthorized"})]

        with self.assertRaises(NeedsFreshToken):
            self.send()

    def test_an_outage_during_a_segment_is_retried(self):
        double = XDouble()
        double.append_failure = FakeResponse(503, {})
        self.http.side_effect = double

        self.send()

        self.assertEqual(double.bytes_received(), CONTENT)

    def test_the_token_never_travels_in_a_url(self):
        self.http.side_effect = XDouble()

        self.send()

        self.assertTrue(all(TOKEN not in call.args[1] for call in self.http.call_args_list))

    def test_an_empty_video_is_refused_before_any_call(self):
        with self.assertRaises(PlatformError) as raised:
            self.send(size=0)
        self.assertEqual(raised.exception.type, FailureType.VALIDATION)
        self.http.assert_not_called()


class XResumeStateScenarios(PlatformTestCase):
    def test_a_state_without_a_segment_size_is_not_resumed(self):
        self.assertIsNone(ResumeState.of({"media_id": MEDIA_ID, "next_segment": 2}))

    def test_a_state_survives_its_dictionary(self):
        state = ResumeState(media_id=MEDIA_ID, segment_bytes=CHUNK, next_segment=3, created_at=10.0)

        self.assertEqual(ResumeState.of(state.as_dict()), state)
