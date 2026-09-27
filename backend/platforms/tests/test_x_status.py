from platforms.http import AUTHORIZATION, FILE, PLATFORM, RATE_LIMIT, PlatformFailure
from platforms.x import NeedsFreshToken, VideoOptions, create_post, failure_of, processing_status, validate
from platforms.x.api import API_ROOT
from platforms.x.status import status_of

from .base import FakeResponse, PlatformTestCase

MEDIA_ID = "1880000000000000001"
POST_ID = "1990000000000000001"
TOKEN = "x.access-token"


def processing(state: str, **extra) -> dict:
    return {"data": {"id": MEDIA_ID, "processing_info": {"state": state, **extra}}}


class XProcessingScenarios(PlatformTestCase):
    def test_the_status_is_asked_with_the_media_id(self):
        # Given: X is still processing
        self.http.side_effect = [FakeResponse(200, processing("in_progress", check_after_secs=5))]

        # When: the status is fetched
        status = processing_status(TOKEN, MEDIA_ID)

        # Then: it is neither ready nor failed, and it was asked in X's STATUS form
        self.assertFalse(status.is_ready or status.is_failed)
        self.assertEqual(self.http.call_args.args[1], f"{API_ROOT}/media/upload")
        self.assertEqual(self.http.call_args.kwargs["params"], {"command": "STATUS", "media_id": MEDIA_ID})

    def test_a_video_without_processing_info_is_ready(self):
        self.assertTrue(status_of({"data": {"id": MEDIA_ID}}).is_ready)

    def test_a_succeeded_video_is_ready(self):
        self.assertTrue(status_of(processing("succeeded")).is_ready)

    def test_a_failed_video_carries_xs_reason(self):
        # Given: X could not process the video
        status = status_of(processing("failed", error={"code": 1, "name": "InvalidMedia", "message": "Bad codec"}))

        # When: it becomes a failure
        failure = failure_of(status)

        # Then: it is about the file, with X's words
        self.assertTrue(status.is_failed)
        self.assertEqual((failure.type, failure.message), (FILE, "Bad codec"))

    def test_a_rejected_token_asks_for_a_fresh_one(self):
        self.http.side_effect = [FakeResponse(401, {"title": "Unauthorized"})]

        with self.assertRaises(NeedsFreshToken):
            processing_status(TOKEN, MEDIA_ID)


class XPostScenarios(PlatformTestCase):
    def test_the_post_carries_the_text_the_video_and_only_the_chosen_options(self):
        # Given: X creates the post
        self.http.side_effect = [FakeResponse(201, {"data": {"id": POST_ID, "text": "A video"}})]
        options = VideoOptions(reply_audience="following", made_with_ai=True)

        # When: the post is created
        post_id = create_post(TOKEN, "A video", MEDIA_ID, options)

        # Then: the body names the video, and the defaults were not sent
        self.assertEqual(post_id, POST_ID)
        self.assertEqual(
            self.http.call_args.kwargs["json"],
            {"text": "A video", "media": {"media_ids": [MEDIA_ID]}, "reply_settings": "following", "made_with_ai": True},
        )

    def test_a_post_is_sent_once_even_when_x_does_not_answer(self):
        # Given: X is unavailable
        self.http.side_effect = [FakeResponse(503, {})] * 5

        # When / Then: the failure is reported after one attempt, so nothing is posted twice
        with self.assertRaises(PlatformFailure) as raised:
            create_post(TOKEN, "A video", MEDIA_ID, VideoOptions())
        self.assertEqual(raised.exception.type, PLATFORM)
        self.assertEqual(self.http.call_count, 1)

    def test_a_duplicate_post_is_a_refusal_with_xs_words(self):
        refusal = {"detail": "You are not allowed to create a Tweet with duplicate content.", "type": "about:blank", "status": 403}
        self.http.side_effect = [FakeResponse(403, refusal)]

        with self.assertRaises(PlatformFailure) as raised:
            create_post(TOKEN, "A video", MEDIA_ID, VideoOptions())
        self.assertEqual(raised.exception.type, AUTHORIZATION)
        self.assertIn("duplicate content", raised.exception.message)

    def test_spent_credits_are_a_limit_that_is_not_retried(self):
        refusal = {"title": "Usage cap exceeded", "type": "https://api.x.com/2/problems/usage-capped", "status": 429}
        self.http.side_effect = [FakeResponse(429, refusal)] * 5

        with self.assertRaises(PlatformFailure) as raised:
            create_post(TOKEN, "A video", MEDIA_ID, VideoOptions())
        self.assertEqual((raised.exception.type, raised.exception.details), (RATE_LIMIT, "usage-capped"))
        self.assertFalse(raised.exception.retryable)

    def test_an_app_without_access_is_told_so(self):
        refusal = {
            "title": "Client Forbidden",
            "detail": "This app is not enrolled",
            "type": "https://api.x.com/2/problems/client-forbidden",
            "reason": "client-not-enrolled",
        }
        self.http.side_effect = [FakeResponse(403, refusal)]

        with self.assertRaises(PlatformFailure) as raised:
            create_post(TOKEN, "A video", MEDIA_ID, VideoOptions())
        self.assertEqual((raised.exception.type, raised.exception.details), (AUTHORIZATION, "client-forbidden"))


class XValidationScenarios(PlatformTestCase):
    def check(self, **kwargs) -> list[str]:
        defaults = {"caption": "A video", "size_bytes": 1000, "mime_type": "video/mp4", "duration_seconds": 30}
        return validate(**{**defaults, **kwargs}).errors

    def test_a_short_clip_is_valid(self):
        self.assertEqual(self.check(), [])

    def test_text_is_counted_in_utf16_units_as_the_browser_counts_it(self):
        self.assertEqual(self.check(caption="a" * 280), [])
        self.assertEqual(self.check(caption="😀" * 140), [])
        self.assertEqual(self.check(caption="😀" * 141), ["captionTooLong"])

    def test_the_desktop_limits_hold(self):
        self.assertEqual(self.check(size_bytes=512 * 1024**2 + 1), ["fileTooLarge"])
        self.assertEqual(self.check(mime_type="video/webm"), ["unsupportedType"])
        self.assertEqual(self.check(duration_seconds=0.4), ["videoTooShort"])
        self.assertEqual(self.check(duration_seconds=140.5), ["videoTooLong"])
