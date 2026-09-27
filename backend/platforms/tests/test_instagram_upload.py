import time

from platforms.http import AUTHENTICATION, FILE, PLATFORM, RATE_LIMIT, PlatformFailure
from platforms.instagram import ReelInfo, ResumeState, upload
from platforms.instagram.api import GRAPH_ROOT, RUPLOAD_ROOT
from platforms.upload import NeedsFreshToken, UploadCancelled

from .base import CHUNK, CONTENT, FakeResponse, PlatformTestCase

IG_USER_ID = "17841400000000001"
CONTAINER_ID = "17900000000000001"
NEW_CONTAINER_ID = "17900000000000002"
TOKEN = "EAAG.page-token"

REEL = ReelInfo(caption="A video\n\n#one", share_to_feed=False, thumb_offset_ms=1500)


class InstagramDouble:
    def __init__(self, status_code="IN_PROGRESS", bytes_transferred=None, container_ids=None, size=len(CONTENT)):
        self.size = size
        self.status_code = status_code
        self.bytes_transferred = bytes_transferred
        self.container_ids = list(container_ids or [CONTAINER_ID])
        self.containers: list[dict] = []
        self.received: list[tuple[str, int, bytes]] = []
        self.chunk_failure = None

    def __call__(self, method, url, **kwargs):
        if url == f"{GRAPH_ROOT}/{IG_USER_ID}/media":
            self.containers.append(kwargs["data"])
            return FakeResponse(200, {"id": self.container_ids.pop(0)})
        if url.startswith(f"{GRAPH_ROOT}/") and method == "GET":
            uploading = {} if self.bytes_transferred is None else {"bytes_transferred": self.bytes_transferred}
            return FakeResponse(
                200, {"status_code": self.status_code, "video_status": {"uploading_phase": uploading}}
            )
        if url.startswith(f"{RUPLOAD_ROOT}/"):
            if self.chunk_failure is not None:
                failure, self.chunk_failure = self.chunk_failure, None
                return failure
            headers = kwargs["headers"]
            self.assert_announces_the_whole_file(headers)
            self.received.append((url.rsplit("/", 1)[1], int(headers["offset"]), kwargs["data"]))
            return FakeResponse(200, {"success": True})
        raise AssertionError(f"unexpected call to {method} {url}")

    def assert_announces_the_whole_file(self, headers):
        if headers["file_size"] != str(self.size) or headers["Authorization"] != f"OAuth {TOKEN}":
            raise AssertionError(f"unexpected headers {headers}")

    def bytes_received(self) -> bytes:
        return b"".join(piece for _, _, piece in self.received)


class InstagramUploadScenarios(PlatformTestCase):
    def send(self, **kwargs):
        defaults = {
            "path": self.given_file(),
            "size": len(CONTENT),
            "ig_user_id": IG_USER_ID,
            "reel": REEL,
            "access_token": TOKEN,
        }
        return upload(**{**defaults, **kwargs})

    def resume_state(self, offset: int, age_seconds: float = 60) -> ResumeState:
        return ResumeState(container_id=CONTAINER_ID, offset=offset, created_at=time.time() - age_seconds)

    def test_the_container_asks_for_a_resumable_reel_with_the_options(self):
        # Given: Instagram accepts everything
        double = InstagramDouble()
        self.http.side_effect = double

        # When: the video is uploaded
        container_id = self.send()

        # Then: one Reels container, with the caption and the options
        self.assertEqual(container_id, CONTAINER_ID)
        self.assertEqual(
            double.containers,
            [
                {
                    "media_type": "REELS",
                    "upload_type": "resumable",
                    "caption": "A video\n\n#one",
                    "share_to_feed": "false",
                    "thumb_offset": "1500",
                }
            ],
        )

    def test_every_byte_goes_once_and_in_order(self):
        double = InstagramDouble()
        self.http.side_effect = double

        self.send()

        self.assertEqual(double.bytes_received(), CONTENT)
        self.assertEqual([offset for _, offset, _ in double.received], list(range(0, len(CONTENT), CHUNK)))

    def test_the_token_never_travels_in_a_url(self):
        self.http.side_effect = InstagramDouble()

        self.send()

        self.assertTrue(all(TOKEN not in call.args[1] for call in self.http.call_args_list))
        self.assertTrue(all("access_token" not in (call.kwargs.get("params") or {}) for call in self.http.call_args_list))

    def test_progress_reports_the_bytes_accepted(self):
        self.http.side_effect = InstagramDouble()
        reports = []

        self.send(on_progress=lambda uploaded, total, state: reports.append(uploaded))

        self.assertEqual(reports[0], CHUNK)
        self.assertEqual(reports[-1], len(CONTENT))

    def test_a_resumed_upload_continues_where_instagram_says_it_stopped(self):
        # Given: a worker died; Instagram holds three chunks, though we recorded two
        double = InstagramDouble(bytes_transferred=3 * CHUNK)
        self.http.side_effect = double

        # When: the upload is run again
        self.send(resume=self.resume_state(offset=2 * CHUNK))

        # Then: no new container, and the rest goes from the fourth chunk
        self.assertEqual(double.containers, [])
        self.assertEqual(double.received[0][1], 3 * CHUNK)
        self.assertEqual(double.bytes_received(), CONTENT[3 * CHUNK :])

    def test_a_resumed_upload_trusts_its_own_offset_when_instagram_does_not_report_one(self):
        double = InstagramDouble(bytes_transferred=None)
        self.http.side_effect = double

        self.send(resume=self.resume_state(offset=2 * CHUNK))

        self.assertEqual(double.received[0][1], 2 * CHUNK)

    def test_an_expired_container_starts_a_new_upload(self):
        # Given: Instagram let the saved container expire
        double = InstagramDouble(status_code="EXPIRED", container_ids=[NEW_CONTAINER_ID])
        self.http.side_effect = double

        # When: the upload is run again
        container_id = self.send(resume=self.resume_state(offset=2 * CHUNK))

        # Then: a new container gets the whole file
        self.assertEqual(container_id, NEW_CONTAINER_ID)
        self.assertEqual(len(double.containers), 1)
        self.assertEqual(double.bytes_received(), CONTENT)

    def test_a_container_older_than_its_lifetime_is_not_asked_about(self):
        double = InstagramDouble(container_ids=[NEW_CONTAINER_ID])
        self.http.side_effect = double

        self.send(resume=self.resume_state(offset=2 * CHUNK, age_seconds=24 * 60 * 60))

        self.assertFalse(any(call.args[0] == "GET" for call in self.http.call_args_list))
        self.assertEqual(double.bytes_received(), CONTENT)

    def test_a_rejected_token_during_the_upload_keeps_the_state(self):
        # Given: Meta rejects the token half way, in its own envelope on a 400
        double = InstagramDouble()
        self.http.side_effect = double
        resume = self.resume_state(offset=2 * CHUNK)
        double.chunk_failure = FakeResponse(
            400, {"error": {"message": "Error validating access token", "code": 190, "error_subcode": 463}}
        )

        # When / Then: a fresh token is asked for, with the place to resume from
        with self.assertRaises(NeedsFreshToken) as raised:
            self.send(resume=resume)
        self.assertEqual(raised.exception.state["container_id"], CONTAINER_ID)
        self.assertEqual(raised.exception.state["offset"], 2 * CHUNK)

    def test_a_rejected_token_at_the_container_asks_for_a_fresh_one(self):
        self.http.side_effect = [FakeResponse(400, {"error": {"message": "expired", "code": 190}})]

        with self.assertRaises(NeedsFreshToken):
            self.send()

    def test_an_error_envelope_on_a_200_is_a_failure_with_its_code(self):
        # Given: Meta answers 200 with an error inside
        self.http.side_effect = [
            FakeResponse(200, {"error": {"message": "Invalid parameter", "code": 100, "error_subcode": 2207026}})
        ]

        # When / Then: the code survives for the person to see
        with self.assertRaises(PlatformFailure) as raised:
            self.send()
        self.assertEqual(raised.exception.details, "100/2207026")
        self.assertEqual(raised.exception.message, "Invalid parameter")

    def test_an_exhausted_quota_is_not_retried(self):
        self.http.side_effect = [FakeResponse(400, {"error": {"message": "Application request limit reached", "code": 4}})]

        with self.assertRaises(PlatformFailure) as raised:
            self.send()
        self.assertEqual(raised.exception.type, RATE_LIMIT)
        self.assertEqual(self.http.call_count, 1)

    def test_a_chunk_lost_to_an_outage_is_sent_again(self):
        double = InstagramDouble()
        self.http.side_effect = double
        double.chunk_failure = FakeResponse(503, {})

        self.send()

        self.assertEqual(double.bytes_received(), CONTENT)

    def test_a_refused_chunk_fails_the_upload(self):
        double = InstagramDouble()
        self.http.side_effect = double
        double.chunk_failure = FakeResponse(
            400, {"debug_info": {"retriable": False, "type": "ProcessingFailedError", "message": "Bad file"}}
        )

        with self.assertRaises(PlatformFailure) as raised:
            self.send()
        self.assertEqual(raised.exception.message, "Bad file")

    def test_a_chunk_answered_without_success_fails(self):
        double = InstagramDouble()
        self.http.side_effect = double
        double.chunk_failure = FakeResponse(200, {"success": False})

        with self.assertRaises(PlatformFailure) as raised:
            self.send()
        self.assertEqual(raised.exception.type, PLATFORM)

    def test_cancelling_keeps_the_state_to_resume_from(self):
        self.http.side_effect = InstagramDouble()
        answers = iter([False, True])

        with self.assertRaises(UploadCancelled) as raised:
            self.send(should_cancel=lambda: next(answers))

        self.assertEqual(raised.exception.state["offset"], CHUNK)

    def test_a_file_shorter_than_declared_fails(self):
        self.http.side_effect = InstagramDouble(size=len(CONTENT) + CHUNK)

        with self.assertRaises(PlatformFailure) as raised:
            self.send(size=len(CONTENT) + CHUNK)
        self.assertEqual(raised.exception.type, FILE)

    def test_the_state_survives_a_round_trip_through_json(self):
        state = self.resume_state(offset=CHUNK)

        self.assertEqual(ResumeState.of(state.as_dict()), state)
        self.assertIsNone(ResumeState.of({"offset": 3}))

    def test_a_401_is_a_rejected_token_too(self):
        self.http.side_effect = [FakeResponse(401, {})]

        with self.assertRaises(NeedsFreshToken):
            self.send()

    def test_a_permission_error_is_not_a_rejected_token(self):
        self.http.side_effect = [FakeResponse(400, {"error": {"message": "Permissions error", "code": 200}})]

        with self.assertRaises(PlatformFailure) as raised:
            self.send()
        self.assertNotEqual(raised.exception.type, AUTHENTICATION)
