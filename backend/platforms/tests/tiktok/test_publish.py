from platforms.core import AwaitingConfirmation, NotReady, PlatformError, PlatformFailure, Published
from platforms.tiktok import TikTokConfig
from platforms.tiktok.core import TikTokEndpoints, TikTokHttp
from platforms.tiktok.creator import TikTokCreatorInfo
from platforms.tiktok.publish import TikTokPublishInteractor
from platforms.tiktok.publish.answers.publish_status import Status
from platforms.tiktok.publish.chunk_plan import ChunkPlan

from ..base import CHUNK, CONTENT, REDIRECT, PlatformTestCase, ok
from ..fakes.http import FakeAnswer

CONFIG = TikTokConfig("client-key", "client-secret", REDIRECT.format(platform="tiktok"), chunk_bytes=CHUNK, retries=2)
TOKEN = "act.token"
PUBLISH_ID = "v_pub_file~v2.123"
UPLOAD_URL = "https://open-upload.tiktokapis.com/video/?upload_id=1"
SETTINGS = {"privacyLevel": "SELF_ONLY"}
OK_ENVELOPE = {"code": "ok", "message": "", "log_id": "log"}


def creator(**fields) -> FakeAnswer:
    data = {
        "creator_username": "creator",
        "privacy_level_options": ["PUBLIC_TO_EVERYONE", "SELF_ONLY"],
        "comment_disabled": False,
        "duet_disabled": False,
        "stitch_disabled": False,
        "max_video_post_duration_sec": 600,
        **fields,
    }
    return ok({"data": data, "error": OK_ENVELOPE})


def initialized() -> FakeAnswer:
    return ok({"data": {"publish_id": PUBLISH_ID, "upload_url": UPLOAD_URL}, "error": OK_ENVELOPE})


def status(state: str, **fields) -> FakeAnswer:
    return ok({"data": {"status": state, **fields}, "error": OK_ENVELOPE})


def chunks_kept(count: int) -> list[FakeAnswer]:
    return [*(FakeAnswer(206) for _ in range(count - 1)), FakeAnswer(201)]


class TikTokTestCase(PlatformTestCase):
    def publishing(self) -> TikTokPublishInteractor:
        http = TikTokHttp(self.http)
        return TikTokPublishInteractor(CONFIG, http, TikTokCreatorInfo(http))


class ChunkPlanScenarios(TikTokTestCase):
    def test_a_file_smaller_than_a_chunk_goes_in_one_piece(self):
        self.assertEqual(ChunkPlan.of(500, CHUNK), ChunkPlan(500, 500, 1))

    def test_the_last_chunk_takes_the_remainder(self):
        plan = ChunkPlan.of(2500, CHUNK)

        self.assertEqual(plan.total_chunks, 2)
        self.assertEqual(plan.bounds_of(1), (1024, 2499))


class TikTokUploadScenarios(TikTokTestCase):
    async def test_the_init_announces_the_chunks_it_will_receive(self):
        # Given: TikTok accepts the init and every chunk
        self.given_answers(creator(), initialized(), *chunks_kept(5))

        # When: the video is uploaded
        events = await self.drain(self.publishing().upload(self.given_job(settings=SETTINGS), TOKEN))

        # Then: the init carried the chunk plan and the post info, and the last event names the publish
        init = self.http.sent[1]
        self.assertEqual(init.url, TikTokEndpoints.VIDEO_INIT)
        self.assertEqual(
            init.json["source_info"],
            {"source": "FILE_UPLOAD", "video_size": len(CONTENT), "chunk_size": CHUNK, "total_chunk_count": 5},
        )
        self.assertEqual(init.json["post_info"]["privacy_level"], "SELF_ONLY")
        self.assertEqual(init.json["post_info"]["title"], "A title\n\nA description")
        self.assertEqual([event.uploaded_bytes for event in events], [0, 1024, 2048, 3072, 4096, 5120])
        self.assertEqual(events[-1].media_id, PUBLISH_ID)
        self.assertEqual([event.media_id for event in events[:-1]], [None] * 5)

    async def test_the_chunks_carry_their_range_and_no_bearer_token(self):
        self.given_answers(creator(), initialized(), *chunks_kept(5))

        await self.drain(self.publishing().upload(self.given_job(settings=SETTINGS), TOKEN))

        chunks = self.http.sent[2:]
        self.assertEqual(
            [chunk.headers["Content-Range"] for chunk in chunks],
            ["bytes 0-1023/5120", "bytes 1024-2047/5120", "bytes 2048-3071/5120", "bytes 3072-4095/5120", "bytes 4096-5119/5120"],
        )
        self.assertTrue(all("Authorization" not in chunk.headers for chunk in chunks))
        self.assertEqual(b"".join(chunk.data for chunk in chunks), CONTENT)

    async def test_a_last_chunk_not_answered_with_201_fails(self):
        self.given_answers(creator(), initialized(), *(FakeAnswer(206) for _ in range(5)))

        with self.assertRaises(PlatformError) as raised:
            await self.drain(self.publishing().upload(self.given_job(settings=SETTINGS), TOKEN))

        self.assertEqual(raised.exception.failure, PlatformFailure.REFUSED)

    async def test_a_chunk_lost_to_an_outage_is_sent_again(self):
        # Given: the second chunk meets an outage once
        self.given_answers(creator(), initialized(), FakeAnswer(206), FakeAnswer(503), *chunks_kept(4))

        # When: the video is uploaded
        events = await self.drain(self.publishing().upload(self.given_job(settings=SETTINGS), TOKEN))

        # Then: the chunk went again with the same range, and the upload finished
        ranges = [sent.headers["Content-Range"] for sent in self.http.sent[2:]]
        self.assertEqual(ranges[1], ranges[2])
        self.assertEqual(events[-1].media_id, PUBLISH_ID)

    async def test_a_privacy_the_creator_is_not_offered_is_refused_before_the_init(self):
        # Given: the creator may not post publicly
        self.given_answers(creator(privacy_level_options=["SELF_ONLY"]))
        job = self.given_job(settings={"privacyLevel": "PUBLIC_TO_EVERYONE"})

        # When / Then: nothing is uploaded and the reason is named
        with self.assertRaises(PlatformError) as raised:
            await self.drain(self.publishing().upload(job, TOKEN))
        self.assertEqual(raised.exception.failure, PlatformFailure.INVALID)
        self.assertEqual(raised.exception.details, "privacyNotOffered")
        self.assertEqual(len(self.http.sent), 1)

    async def test_a_video_longer_than_the_creator_may_post_is_refused(self):
        self.given_answers(creator(max_video_post_duration_sec=60))

        with self.assertRaises(PlatformError) as raised:
            await self.drain(self.publishing().upload(self.given_job(settings=SETTINGS, duration_seconds=61), TOKEN))

        self.assertEqual(raised.exception.details, "videoTooLong")

    async def test_the_creators_settings_win_over_the_draft(self):
        self.given_answers(creator(comment_disabled=True), initialized(), *chunks_kept(5))

        await self.drain(self.publishing().upload(self.given_job(settings=SETTINGS), TOKEN))

        self.assertTrue(self.http.sent[1].json["post_info"]["disable_comment"])

    async def test_a_rejected_token_at_init_asks_for_a_fresh_one(self):
        self.given_answers(FakeAnswer(401, {"error": {"code": "access_token_invalid", "message": "expired"}}))

        with self.assertRaises(PlatformError) as raised:
            await self.drain(self.publishing().upload(self.given_job(settings=SETTINGS), TOKEN))

        self.assertEqual(raised.exception.failure, PlatformFailure.TOKEN_REJECTED)

    async def test_a_file_shorter_than_declared_fails(self):
        self.given_answers(creator(), initialized())
        job = self.given_job(self.given_file(b"short"), size_bytes=len(CONTENT), settings=SETTINGS)

        with self.assertRaises(PlatformError) as raised:
            await self.drain(self.publishing().upload(job, TOKEN))

        self.assertEqual(raised.exception.failure, PlatformFailure.MEDIA_MISSING)


class TikTokConfirmationScenarios(TikTokTestCase):
    async def test_publishing_waits_for_tiktok(self):
        self.assertEqual(await self.publishing().publish(self.given_job(media_id=PUBLISH_ID), TOKEN), AwaitingConfirmation())

    async def test_a_finished_post_links_to_its_public_id(self):
        # Given: TikTok finished the post and the creator's username is known
        self.given_answers(status("PUBLISH_COMPLETE", publicaly_available_post_id=[7300000000000000001]), creator())

        # When: the publish is confirmed
        outcome = await self.publishing().confirm(self.given_job(media_id=PUBLISH_ID), TOKEN)

        # Then: the link points at the post, and the status was asked for this publish
        self.assertEqual(outcome, Published("https://www.tiktok.com/@creator/video/7300000000000000001"))
        self.assertEqual(self.http.sent[0].json, {"publish_id": PUBLISH_ID})

    async def test_a_post_sent_to_the_inbox_is_complete_without_a_link(self):
        self.given_answers(status("SEND_TO_USER_INBOX"))

        self.assertEqual(await self.publishing().confirm(self.given_job(media_id=PUBLISH_ID), TOKEN), Published(""))

    async def test_an_unknown_username_leaves_the_link_out(self):
        self.given_answers(status("PUBLISH_COMPLETE", publicaly_available_post_id=[1]), FakeAnswer(503))

        self.assertEqual(await self.publishing().confirm(self.given_job(media_id=PUBLISH_ID), TOKEN), Published(""))

    async def test_a_post_still_processing_is_not_ready(self):
        self.given_answers(status("PROCESSING_UPLOAD"))

        self.assertEqual(await self.publishing().confirm(self.given_job(media_id=PUBLISH_ID), TOKEN), NotReady())

    async def test_a_failed_post_reports_why(self):
        self.given_answers(status("FAILED", fail_reason="duration_check_failed"))

        with self.assertRaises(PlatformError) as raised:
            await self.publishing().confirm(self.given_job(media_id=PUBLISH_ID), TOKEN)

        self.assertEqual(raised.exception.failure, PlatformFailure.FILE_REJECTED)
        self.assertEqual(raised.exception.details, "duration_check_failed")

    def test_every_known_fail_reason_has_its_own_message(self):
        messages = [message for _, message in Status.FAIL_REASONS.values()]

        self.assertEqual(len(messages), len(set(messages)))

    def test_an_unknown_reason_is_a_refusal(self):
        failure = Status(status="FAILED", fail_reason="something_new").failure()

        self.assertEqual((failure.failure, failure.details), (PlatformFailure.REFUSED, "something_new"))

    async def test_a_rejected_token_asks_for_a_fresh_one(self):
        self.given_answers(FakeAnswer(401, {"error": {"code": "access_token_invalid", "message": "expired"}}))

        with self.assertRaises(PlatformError) as raised:
            await self.publishing().confirm(self.given_job(media_id=PUBLISH_ID), TOKEN)

        self.assertEqual(raised.exception.failure, PlatformFailure.TOKEN_REJECTED)
