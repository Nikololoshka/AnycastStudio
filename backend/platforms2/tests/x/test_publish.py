from platforms2.core import AwaitingConfirmation, NotReady, PlatformError, PlatformFailure, Published, ReadyToCommit
from platforms2.x import XConfig
from platforms2.x.core import XEndpoints, XHttp
from platforms2.x.publish import XPublishInteractor

from ..base import CHUNK, CONTENT, REDIRECT, PlatformTestCase, ok
from ..fakes.http import FakeAnswer, SentRequest

CONFIG = XConfig("x-client-id", "x-secret", REDIRECT.format(platform="x"), segment_bytes=CHUNK, retries=2)
TOKEN = "x.access"
MEDIA_ID = "1880000000000000001"
POST_ID = "1990000000000000001"


def created(identifier: str = MEDIA_ID) -> FakeAnswer:
    return ok({"data": {"id": identifier}})


def processing(state: str, **extra) -> FakeAnswer:
    return ok({"data": {"id": MEDIA_ID, "processing_info": {"state": state, **extra}}})


def form_of(sent: SentRequest) -> dict:
    return {options["name"]: value for options, _, value in sent.data._fields}


class XTestCase(PlatformTestCase):
    def publishing(self) -> XPublishInteractor:
        return XPublishInteractor(CONFIG, XHttp(self.http))


class XUploadScenarios(XTestCase):
    async def test_the_upload_announces_the_whole_video_as_a_post_video(self):
        self.given_answers(created(), *(ok() for _ in range(5)), created())

        await self.drain(self.publishing().upload(self.given_job(), TOKEN))

        self.assertEqual(self.http.sent[0].url, XEndpoints.MEDIA_INITIALIZE)
        self.assertEqual(
            self.http.sent[0].json, {"media_type": "video/mp4", "total_bytes": len(CONTENT), "media_category": "tweet_video"}
        )

    async def test_every_byte_goes_once_and_in_order(self):
        # Given: X accepts every segment and the finalize
        self.given_answers(created(), *(ok() for _ in range(5)), created())

        # When: the video is uploaded
        events = await self.drain(self.publishing().upload(self.given_job(), TOKEN))

        # Then: the segments carry their index and the bytes in order, and the media is finalized last
        segments = [form_of(sent) for sent in self.http.sent[1:6]]
        self.assertEqual([segment["segment_index"] for segment in segments], ["0", "1", "2", "3", "4"])
        self.assertEqual(b"".join(segment["media"] for segment in segments), CONTENT)
        self.assertEqual(self.http.sent[6].url, XEndpoints.media_finalize(MEDIA_ID))
        self.assertEqual([event.uploaded_bytes for event in events], [0, 1024, 2048, 3072, 4096, 5120, 5120])
        self.assertEqual(events[-1].media_id, MEDIA_ID)
        self.assertEqual([event.media_id for event in events[:-1]], [None] * 6)

    async def test_a_last_segment_shorter_than_the_rest_is_sent_whole(self):
        self.given_answers(created(), ok(), ok(), created())

        await self.drain(self.publishing().upload(self.given_job(self.given_file(b"x" * 1500)), TOKEN))

        self.assertEqual([len(form_of(sent)["media"]) for sent in self.http.sent[1:3]], [1024, 476])

    async def test_an_outage_during_a_segment_is_retried(self):
        self.given_answers(created(), ok(), FakeAnswer(503), *(ok() for _ in range(4)), created())

        events = await self.drain(self.publishing().upload(self.given_job(), TOKEN))

        self.assertEqual([form_of(sent)["segment_index"] for sent in self.http.sent[1:7]], ["0", "1", "1", "2", "3", "4"])
        self.assertEqual(events[-1].media_id, MEDIA_ID)

    async def test_a_refused_file_is_not_retried(self):
        self.given_answers(created(), FakeAnswer(400, {"title": "Invalid Request", "detail": "Bad media"}))

        with self.assertRaises(PlatformError) as raised:
            await self.drain(self.publishing().upload(self.given_job(), TOKEN))

        self.assertEqual(raised.exception.failure, PlatformFailure.REFUSED)
        self.assertEqual(len(self.http.sent), 2)

    async def test_the_token_never_travels_in_a_url(self):
        self.given_answers(created(), *(ok() for _ in range(5)), created())

        await self.drain(self.publishing().upload(self.given_job(), TOKEN))

        self.assertTrue(all(TOKEN not in sent.url for sent in self.http.sent))
        self.assertTrue(all(sent.headers["Authorization"] == f"Bearer {TOKEN}" for sent in self.http.sent))

    async def test_an_expired_token_at_the_start_asks_for_a_fresh_one(self):
        self.given_answers(FakeAnswer(401, {"title": "Unauthorized", "detail": "Unauthorized"}))

        with self.assertRaises(PlatformError) as raised:
            await self.drain(self.publishing().upload(self.given_job(), TOKEN))

        self.assertEqual(raised.exception.failure, PlatformFailure.TOKEN_REJECTED)

    async def test_an_empty_video_is_refused_before_any_call(self):
        with self.assertRaises(PlatformError) as raised:
            await self.drain(self.publishing().upload(self.given_job(self.given_file(b"")), TOKEN))

        self.assertEqual(raised.exception.failure, PlatformFailure.INVALID)
        self.assertEqual(self.http.sent, [])


class XConfirmationScenarios(XTestCase):
    def job(self, **fields):
        return self.given_job(media_id=MEDIA_ID, **fields)

    async def test_publishing_waits_for_x(self):
        self.assertEqual(await self.publishing().publish(self.job(), TOKEN), AwaitingConfirmation())

    async def test_the_status_is_asked_with_the_media_id(self):
        self.given_answers(processing("in_progress", check_after_secs=5))

        self.assertEqual(await self.publishing().confirm(self.job(), TOKEN), NotReady())
        self.assertEqual(self.http.last.url, XEndpoints.MEDIA_UPLOAD)
        self.assertEqual(self.http.last.params, {"command": "STATUS", "media_id": MEDIA_ID})

    async def test_a_processed_video_is_ready_to_commit(self):
        self.given_answers(processing("succeeded"))

        self.assertEqual(await self.publishing().confirm(self.job(), TOKEN), ReadyToCommit())

    async def test_a_video_without_processing_info_is_ready_to_commit(self):
        self.given_answers(ok({"data": {"id": MEDIA_ID}}))

        self.assertEqual(await self.publishing().confirm(self.job(), TOKEN), ReadyToCommit())

    async def test_a_failed_video_carries_xs_reason(self):
        self.given_answers(processing("failed", error={"code": 1, "name": "InvalidMedia", "message": "Bad codec"}))

        with self.assertRaises(PlatformError) as raised:
            await self.publishing().confirm(self.job(), TOKEN)

        self.assertEqual(raised.exception.failure, PlatformFailure.FILE_REJECTED)
        self.assertEqual(raised.exception.message, "Bad codec")

    async def test_the_post_carries_the_text_the_video_and_only_the_chosen_options(self):
        # Given: X creates the post
        self.given_answers(created(POST_ID))
        job = self.job(title="Title", description="", hashtags=("a",), settings={"replyAudience": "following", "madeWithAi": True})

        # When: the post is committed
        outcome = await self.publishing().commit(job, TOKEN)

        # Then: the post links to itself and carried exactly the chosen fields, sent once
        self.assertEqual(outcome, Published(f"https://x.com/i/web/status/{POST_ID}"))
        self.assertEqual(
            self.http.last.json,
            {"text": "Title\n\n#a", "media": {"media_ids": [MEDIA_ID]}, "reply_settings": "following", "made_with_ai": True},
        )
        self.assertEqual(len(self.http.sent), 1)

    async def test_a_post_is_sent_once_even_when_x_does_not_answer(self):
        self.given_answers(FakeAnswer(503))

        with self.assertRaises(PlatformError) as raised:
            await self.publishing().commit(self.job(), TOKEN)

        self.assertEqual(raised.exception.failure, PlatformFailure.NETWORK)
        self.assertEqual(len(self.http.sent), 1)

    async def test_a_duplicate_post_is_a_refusal_with_xs_words(self):
        self.given_answers(FakeAnswer(403, {"detail": "You are not allowed to create a Tweet with duplicate content.", "status": 403}))

        with self.assertRaises(PlatformError) as raised:
            await self.publishing().commit(self.job(), TOKEN)

        self.assertEqual(raised.exception.failure, PlatformFailure.REFUSED)
        self.assertIn("duplicate content", raised.exception.message)

    async def test_spent_credits_are_a_limit(self):
        self.given_answers(FakeAnswer(429, {"type": "https://api.x.com/2/problems/usage-capped", "title": "Usage cap exceeded"}))

        with self.assertRaises(PlatformError) as raised:
            await self.publishing().commit(self.job(), TOKEN)

        self.assertEqual(raised.exception.failure, PlatformFailure.RATE_LIMITED)

    async def test_an_app_without_access_is_misconfigured(self):
        self.given_answers(FakeAnswer(403, {"type": "https://api.x.com/2/problems/client-forbidden", "title": "Client Forbidden"}))

        with self.assertRaises(PlatformError) as raised:
            await self.publishing().commit(self.job(), TOKEN)

        self.assertEqual(raised.exception.failure, PlatformFailure.MISCONFIGURED)
