import time

from platforms.core.errors import FailureType, NeedsFreshToken, PlatformError, UploadCancelled
from platforms.core.ports import SystemClock
from platforms.tiktok.client import TikTokClient
from platforms.tiktok.upload import ChunkPlan, DirectPostProtocol, PostInfo, ResumeState, TikTokUploader
from platforms.tiktok.upload.protocol import INIT_ENDPOINT

from ..base import CHUNK, CONTENT, TEST_CONFIG, FakeResponse, PlatformTestCase

UPLOAD_URL = "https://open-upload.tiktokapis.com/video/?upload_id=1"
PUBLISH_ID = "v_pub_file~v2-1.123"

POST_INFO = PostInfo(
    title="A video\n\n#one",
    privacy_level="SELF_ONLY",
    disable_comment=False,
    disable_duet=True,
    disable_stitch=False,
    brand_content_toggle=False,
    brand_organic_toggle=False,
    is_aigc=False,
)


def initialised() -> FakeResponse:
    return FakeResponse(
        200, {"data": {"publish_id": PUBLISH_ID, "upload_url": UPLOAD_URL}, "error": {"code": "ok"}}
    )


class TikTokDouble:
    def __init__(self, final_status=201):
        self.final_status = final_status
        self.received: list[tuple[int, int]] = []
        self.inits = 0

    def __call__(self, method, url, **kwargs):
        if url == INIT_ENDPOINT:
            self.inits += 1
            return initialised()
        first, last = kwargs["headers"]["Content-Range"].split(" ")[1].split("/")[0].split("-")
        self.received.append((int(first), int(last)))
        if int(last) == len(CONTENT) - 1:
            return FakeResponse(self.final_status)
        return FakeResponse(206)


class TikTokUploadScenarios(PlatformTestCase):
    def send(self, **kwargs):
        defaults = {
            "path": self.given_file(),
            "size": len(CONTENT),
            "mime_type": "video/mp4",
            "post_info": POST_INFO,
            "access_token": "act.token",
        }
        uploader = TikTokUploader(DirectPostProtocol(TikTokClient(TEST_CONFIG.http)), TEST_CONFIG.upload, SystemClock())
        return uploader.upload(**{**defaults, **kwargs})

    def test_a_file_smaller_than_a_chunk_goes_in_one_piece(self):
        self.assertEqual(ChunkPlan.of(500, CHUNK), ChunkPlan(500, 1))

    def test_the_last_chunk_takes_the_remainder(self):
        # TikTok counts chunks by rounding down; the remainder rides on the last one
        self.assertEqual(ChunkPlan.of(CHUNK * 3 + 100, CHUNK), ChunkPlan(CHUNK, 3))

    def test_the_init_announces_the_chunks_it_will_receive(self):
        # Given: TikTok accepts everything
        double = TikTokDouble()
        self.http.side_effect = double

        # When: the video is uploaded
        publish_id = self.send()

        # Then: the init matched the chunks sent, and every byte went once in order
        init = self.http.call_args_list[0].kwargs["json"]
        self.assertEqual(init["source_info"]["source"], "FILE_UPLOAD")
        self.assertEqual(init["source_info"]["video_size"], len(CONTENT))
        self.assertEqual(init["source_info"]["chunk_size"], CHUNK)
        self.assertEqual(init["source_info"]["total_chunk_count"], len(CONTENT) // CHUNK)
        self.assertEqual(init["post_info"]["privacy_level"], "SELF_ONLY")
        self.assertEqual(double.received[0], (0, CHUNK - 1))
        self.assertEqual(double.received[-1][1], len(CONTENT) - 1)
        self.assertEqual(publish_id, PUBLISH_ID)

    def test_the_chunks_carry_no_bearer_token(self):
        self.http.side_effect = TikTokDouble()

        self.send()

        puts = [call for call in self.http.call_args_list if call.args[0] == "PUT"]
        self.assertTrue(all("Authorization" not in call.kwargs["headers"] for call in puts))

    def test_a_last_chunk_not_answered_with_201_fails(self):
        # Given: TikTok answers 206 to the final chunk
        self.http.side_effect = TikTokDouble(final_status=206)

        # When / Then: the upload is not reported as complete
        with self.assertRaises(PlatformError) as raised:
            self.send()
        self.assertEqual(raised.exception.type, FailureType.PLATFORM)

    def test_progress_reports_whole_chunks(self):
        self.http.side_effect = TikTokDouble()
        reports = []

        self.send(on_progress=lambda uploaded, total, state: reports.append(uploaded))

        self.assertEqual(reports[0], CHUNK)
        self.assertEqual(reports[-1], len(CONTENT))

    def test_a_live_upload_resumes_at_the_next_chunk_without_a_new_init(self):
        # Given: a worker died after two chunks, well inside the upload URL's lifetime
        double = TikTokDouble()
        self.http.side_effect = double
        resume = ResumeState(
            publish_id=PUBLISH_ID,
            upload_url=UPLOAD_URL,
            chunk_size=CHUNK,
            total_chunks=len(CONTENT) // CHUNK,
            next_chunk=2,
            expires_at=time.time() + 600,
        )

        # When: the upload is run again
        self.send(resume=resume)

        # Then: it continued from the third chunk
        self.assertEqual(double.inits, 0)
        self.assertEqual(double.received[0], (2 * CHUNK, 3 * CHUNK - 1))

    def test_an_expired_upload_url_starts_a_new_upload(self):
        # Given: the saved upload URL has expired
        double = TikTokDouble()
        self.http.side_effect = double
        resume = ResumeState(PUBLISH_ID, UPLOAD_URL, CHUNK, len(CONTENT) // CHUNK, 2, time.time() - 1)

        # When: the upload is run again
        self.send(resume=resume)

        # Then: TikTok was asked for a new upload, sent from the first byte
        self.assertEqual(double.inits, 1)
        self.assertEqual(double.received[0], (0, CHUNK - 1))

    def test_a_rejected_token_at_init_asks_for_a_fresh_one(self):
        self.http.side_effect = [FakeResponse(401, {"error": {"code": "access_token_invalid", "message": "expired"}})]

        with self.assertRaises(NeedsFreshToken):
            self.send()

    def test_an_error_envelope_at_init_carries_the_code(self):
        # Given: TikTok refuses the post in a 403 with its own error code
        self.http.side_effect = [
            FakeResponse(403, {"error": {"code": "spam_risk_too_many_posts", "message": "Too many posts"}})
        ]

        # When / Then: the code survives for the person to see
        with self.assertRaises(PlatformError) as raised:
            self.send()
        self.assertEqual(raised.exception.details, "spam_risk_too_many_posts")

    def test_cancelling_keeps_the_state_to_resume_from(self):
        self.http.side_effect = TikTokDouble()
        answers = iter([False, True])

        with self.assertRaises(UploadCancelled) as raised:
            self.send(should_cancel=lambda: next(answers))

        self.assertEqual(raised.exception.state["next_chunk"], 1)

    def test_a_file_shorter_than_declared_fails(self):
        self.http.side_effect = TikTokDouble()

        with self.assertRaises(PlatformError) as raised:
            self.send(size=len(CONTENT) + CHUNK)
        self.assertEqual(raised.exception.type, FailureType.FILE)
