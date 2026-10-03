from platforms2.core import AwaitingConfirmation, NotReady, PlatformError, PlatformFailure, Published
from platforms2.instagram import InstagramConfig
from platforms2.instagram.core import InstagramEndpoints, InstagramHttp
from platforms2.instagram.publish import InstagramPublishInteractor

from ..base import CHUNK, CONTENT, REDIRECT, PlatformTestCase, ok
from ..fakes.http import FakeAnswer

CONFIG = InstagramConfig("app-id", "app-secret", REDIRECT.format(platform="instagram"), chunk_bytes=CHUNK, retries=2)
TOKEN = "page-token"
IG_USER = "ig-1"
CONTAINER = "container-1"


def kept() -> FakeAnswer:
    return ok({"success": True})


def container(status_code: str, status: str = "") -> FakeAnswer:
    return ok({"status_code": status_code, "status": status, "id": CONTAINER})


class InstagramTestCase(PlatformTestCase):
    def publishing(self) -> InstagramPublishInteractor:
        return InstagramPublishInteractor(CONFIG, InstagramHttp(self.http))


class InstagramUploadScenarios(InstagramTestCase):
    async def test_the_container_asks_for_a_resumable_reel_with_the_options(self):
        # Given: Instagram creates the container and keeps every piece
        self.given_answers(ok({"id": CONTAINER}), *(kept() for _ in range(5)))
        job = self.given_job(
            title="Title", description="", hashtags=("a",), external_id=IG_USER,
            settings={"shareToFeed": False, "coverFrameSeconds": 2.5},
        )

        # When: the video is uploaded
        await self.drain(self.publishing().upload(job, TOKEN))

        # Then: the container is a resumable reel with the caption and the chosen options
        created = self.http.sent[0]
        self.assertEqual(created.url, InstagramEndpoints.media(IG_USER))
        self.assertEqual(
            created.data,
            {"media_type": "REELS", "upload_type": "resumable", "caption": "Title\n\n#a", "share_to_feed": "false", "thumb_offset": "2500"},
        )

    async def test_every_byte_goes_once_and_in_order(self):
        self.given_answers(ok({"id": CONTAINER}), *(kept() for _ in range(5)))

        events = await self.drain(self.publishing().upload(self.given_job(external_id=IG_USER), TOKEN))

        pieces = self.http.sent[1:]
        self.assertEqual(b"".join(piece.data for piece in pieces), CONTENT)
        self.assertEqual([piece.headers["offset"] for piece in pieces], ["0", "1024", "2048", "3072", "4096"])
        self.assertTrue(all(piece.headers["file_size"] == str(len(CONTENT)) for piece in pieces))
        self.assertTrue(all(piece.url == InstagramEndpoints.rupload(CONTAINER) for piece in pieces))
        self.assertEqual([event.uploaded_bytes for event in events], [0, 1024, 2048, 3072, 4096, 5120])
        self.assertEqual(events[-1].media_id, CONTAINER)

    async def test_the_token_never_travels_in_a_url(self):
        self.given_answers(ok({"id": CONTAINER}), *(kept() for _ in range(5)))

        await self.drain(self.publishing().upload(self.given_job(external_id=IG_USER), TOKEN))

        self.assertTrue(all(TOKEN not in sent.url and TOKEN not in str(sent.params) for sent in self.http.sent))
        self.assertTrue(all(sent.headers["Authorization"] == f"OAuth {TOKEN}" for sent in self.http.sent))

    async def test_a_chunk_lost_to_an_outage_is_sent_again(self):
        self.given_answers(ok({"id": CONTAINER}), kept(), FakeAnswer(503), *(kept() for _ in range(4)))

        events = await self.drain(self.publishing().upload(self.given_job(external_id=IG_USER), TOKEN))

        self.assertEqual([piece.headers["offset"] for piece in self.http.sent[1:]], ["0", "1024", "1024", "2048", "3072", "4096"])
        self.assertEqual(events[-1].media_id, CONTAINER)

    async def test_a_chunk_answered_without_success_fails(self):
        self.given_answers(ok({"id": CONTAINER}), ok({"success": False}))

        with self.assertRaises(PlatformError) as raised:
            await self.drain(self.publishing().upload(self.given_job(external_id=IG_USER), TOKEN))

        self.assertEqual(raised.exception.failure, PlatformFailure.REFUSED)

    async def test_an_error_envelope_on_a_200_is_a_failure_with_its_code(self):
        self.given_answers(ok({"error": {"code": 190, "message": "Session expired"}}))

        with self.assertRaises(PlatformError) as raised:
            await self.drain(self.publishing().upload(self.given_job(external_id=IG_USER), TOKEN))

        self.assertEqual(raised.exception.failure, PlatformFailure.TOKEN_REJECTED)
        self.assertIn("Session expired", raised.exception.message)

    async def test_a_permission_error_is_not_a_rejected_token(self):
        self.given_answers(FakeAnswer(403, {"error": {"code": 10, "message": "Permission denied"}}))

        with self.assertRaises(PlatformError) as raised:
            await self.drain(self.publishing().upload(self.given_job(external_id=IG_USER), TOKEN))

        self.assertEqual(raised.exception.failure, PlatformFailure.SCOPE_MISSING)

    async def test_an_empty_video_is_refused_before_any_call(self):
        with self.assertRaises(PlatformError) as raised:
            await self.drain(self.publishing().upload(self.given_job(self.given_file(b"")), TOKEN))

        self.assertEqual(raised.exception.failure, PlatformFailure.INVALID)
        self.assertEqual(self.http.sent, [])

    async def test_a_file_shorter_than_declared_fails(self):
        self.given_answers(ok({"id": CONTAINER}))
        job = self.given_job(self.given_file(b"short"), size_bytes=len(CONTENT))

        with self.assertRaises(PlatformError) as raised:
            await self.drain(self.publishing().upload(job, TOKEN))

        self.assertEqual(raised.exception.failure, PlatformFailure.MEDIA_MISSING)


class InstagramConfirmationScenarios(InstagramTestCase):
    def job(self):
        return self.given_job(media_id=CONTAINER, external_id=IG_USER)

    async def test_publishing_waits_for_instagram(self):
        self.assertEqual(await self.publishing().publish(self.job(), TOKEN), AwaitingConfirmation())

    async def test_a_container_still_processing_is_not_ready(self):
        self.given_answers(container("IN_PROGRESS"))

        self.assertEqual(await self.publishing().confirm(self.job(), TOKEN), NotReady())

    async def test_a_finished_container_is_published_and_linked(self):
        # Given: the container is ready, Instagram publishes it and knows its link
        self.given_answers(container("FINISHED"), ok({"id": "media-1"}), ok({"permalink": "https://instagram.com/reel/1"}))

        # When: the publish is confirmed
        outcome = await self.publishing().confirm(self.job(), TOKEN)

        # Then: the container was published once, and the link is the reel's
        self.assertEqual(outcome, Published("https://instagram.com/reel/1"))
        publish = self.http.sent[1]
        self.assertEqual(publish.url, InstagramEndpoints.media_publish(IG_USER))
        self.assertEqual(publish.data, {"creation_id": CONTAINER})

    async def test_a_publish_that_did_not_answer_is_asked_about_again(self):
        self.given_answers(container("FINISHED"), FakeAnswer(503))

        self.assertEqual(await self.publishing().confirm(self.job(), TOKEN), NotReady())
        self.assertEqual(len(self.http.sent), 2)

    async def test_an_already_published_container_is_published(self):
        self.given_answers(container("PUBLISHED"))

        self.assertEqual(await self.publishing().confirm(self.job(), TOKEN), Published())
        self.assertEqual(len(self.http.sent), 1)

    async def test_an_unknown_link_leaves_it_out(self):
        self.given_answers(container("FINISHED"), ok({"id": "media-1"}), FakeAnswer(500))

        self.assertEqual(await self.publishing().confirm(self.job(), TOKEN), Published(""))

    async def test_an_errored_container_fails_with_instagrams_words(self):
        self.given_answers(container("ERROR", "Video codec is not supported"))

        with self.assertRaises(PlatformError) as raised:
            await self.publishing().confirm(self.job(), TOKEN)

        self.assertEqual(raised.exception.failure, PlatformFailure.FILE_REJECTED)
        self.assertEqual(raised.exception.details, "Video codec is not supported")

    async def test_an_expired_container_fails_as_expired(self):
        self.given_answers(container("EXPIRED"))

        with self.assertRaises(PlatformError) as raised:
            await self.publishing().confirm(self.job(), TOKEN)

        self.assertEqual((raised.exception.failure, raised.exception.details), (PlatformFailure.REFUSED, "EXPIRED"))

    async def test_a_publish_refused_by_instagram_fails(self):
        self.given_answers(container("FINISHED"), FakeAnswer(400, {"error": {"code": 9007, "message": "Media not ready"}}))

        with self.assertRaises(PlatformError) as raised:
            await self.publishing().confirm(self.job(), TOKEN)

        self.assertIn("Media not ready", raised.exception.message)
