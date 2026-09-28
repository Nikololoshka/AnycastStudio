import requests

from platforms.core.errors import FailureType, NeedsFreshToken, PlatformError
from platforms.core.publishing import MediaInfo, PublicationDraft
from platforms.instagram.client import GRAPH_ROOT, InstagramClient
from platforms.instagram.options import InstagramOptions, InstagramValidator
from platforms.instagram.options.capabilities import MAX_FILE_BYTES
from platforms.instagram.publish import ContainerApi

from ..base import TEST_CONFIG, FakeResponse, PlatformTestCase

TOKEN = "EAAG.page-token"
CONTAINER_ID = "17900000000000001"


def containers() -> ContainerApi:
    return ContainerApi(InstagramClient(TEST_CONFIG.http))


def fetch_status(access_token: str, container_id: str):
    return containers().status(access_token, container_id)


def publish_container(access_token: str, ig_user_id: str, container_id: str) -> str:
    return containers().publish(access_token, ig_user_id, container_id)


def validate(*, caption: str, size_bytes: int, mime_type: str, duration_seconds: float | None):
    draft = PublicationDraft(caption, "", (), MediaInfo(size_bytes, mime_type, duration_seconds))
    return InstagramValidator().validate(draft)


class ContainerStatusScenarios(PlatformTestCase):
    def test_a_finished_container_is_ready(self):
        self.http.side_effect = [FakeResponse(200, {"status_code": "FINISHED", "status": "Finished: Media has been uploaded"})]

        status = fetch_status(TOKEN, CONTAINER_ID)

        self.assertTrue(status.is_ready)
        self.assertEqual(self.http.call_args.args[1], f"{GRAPH_ROOT}/{CONTAINER_ID}")

    def test_an_errored_container_fails_with_instagrams_words(self):
        self.http.side_effect = [
            FakeResponse(200, {"status_code": "ERROR", "status": "Error: Media upload has failed with error code 2207026"})
        ]

        status = fetch_status(TOKEN, CONTAINER_ID)
        failure = status.failure()

        self.assertTrue(status.is_dead)
        self.assertEqual(failure.type, FailureType.FILE)
        self.assertEqual(failure.details, "Error: Media upload has failed with error code 2207026")

    def test_an_expired_container_fails_as_expired(self):
        self.http.side_effect = [FakeResponse(200, {"status_code": "EXPIRED"})]

        failure = fetch_status(TOKEN, CONTAINER_ID).failure()

        self.assertEqual((failure.type, failure.details), (FailureType.PLATFORM, "EXPIRED"))

    def test_a_rejected_token_asks_for_a_fresh_one(self):
        self.http.side_effect = [FakeResponse(400, {"error": {"message": "expired", "code": 190}})]

        with self.assertRaises(NeedsFreshToken):
            fetch_status(TOKEN, CONTAINER_ID)


class PublishScenarios(PlatformTestCase):
    def test_publishing_answers_the_media_id(self):
        self.http.side_effect = [FakeResponse(200, {"id": "18000000000000001"})]

        media_id = publish_container(TOKEN, "17841400000000001", CONTAINER_ID)

        self.assertEqual(media_id, "18000000000000001")
        self.assertEqual(self.http.call_args.kwargs["data"], {"creation_id": CONTAINER_ID})

    def test_publishing_is_never_sent_twice(self):
        # Given: the first answer is lost, and a second send might post the reel twice
        self.http.side_effect = [FakeResponse(503, {})] * 3

        # When / Then: it fails once, and the caller decides
        with self.assertRaises(PlatformError) as raised:
            publish_container(TOKEN, "17841400000000001", CONTAINER_ID)
        self.assertTrue(raised.exception.retryable)
        self.assertEqual(self.http.call_count, 1)

    def test_a_publish_without_an_id_is_a_failure(self):
        self.http.side_effect = [FakeResponse(200, {})]

        with self.assertRaises(PlatformError):
            publish_container(TOKEN, "17841400000000001", CONTAINER_ID)

    def test_a_network_error_reports_only_its_class(self):
        self.http.side_effect = requests.ConnectionError(f"https://graph.facebook.com/?access_token={TOKEN}")

        with self.assertRaises(PlatformError) as raised:
            publish_container(TOKEN, "17841400000000001", CONTAINER_ID)
        self.assertEqual(raised.exception.type, FailureType.NETWORK)
        self.assertNotIn(TOKEN, raised.exception.message)


class ValidationScenarios(PlatformTestCase):
    def check(self, **overrides):
        values = {"caption": "A video", "size_bytes": 1024, "mime_type": "video/mp4", "duration_seconds": 30}
        return validate(**{**values, **overrides})

    def test_a_plain_reel_is_valid(self):
        self.assertTrue(self.check().valid)

    def test_each_limit_has_its_own_error(self):
        cases = {
            "captionTooLong": {"caption": "a" * 2201},
            "tooManyHashtags": {"caption": " ".join(f"#tag{index}" for index in range(31))},
            "fileTooLarge": {"size_bytes": MAX_FILE_BYTES + 1},
            "unsupportedType": {"mime_type": "video/webm"},
            "videoTooShort": {"duration_seconds": 2},
            "videoTooLong": {"duration_seconds": 15 * 60 + 1},
        }
        for error, overrides in cases.items():
            with self.subTest(error):
                self.assertEqual(self.check(**overrides).errors, [error])

    def test_thirty_hashtags_are_allowed(self):
        self.assertTrue(self.check(caption=" ".join(f"#tag{index}" for index in range(30))).valid)

    def test_an_unknown_duration_is_left_to_instagram(self):
        self.assertTrue(self.check(duration_seconds=None).valid)


class OptionScenarios(PlatformTestCase):
    def test_missing_options_fall_back_to_the_defaults(self):
        options = InstagramOptions.of({})

        self.assertEqual(options.as_json(), {"shareToFeed": True, "coverFrameSeconds": 0})
        self.assertEqual(options.thumb_offset_ms, 0)

    def test_nonsense_falls_back_rather_than_failing(self):
        options = InstagramOptions.of({"shareToFeed": "no", "coverFrameSeconds": -4})

        self.assertEqual((options.share_to_feed, options.cover_frame_seconds), (True, 0))

    def test_the_cover_frame_is_sent_in_milliseconds(self):
        self.assertEqual(InstagramOptions.of({"coverFrameSeconds": 2.5}).thumb_offset_ms, 2500)
