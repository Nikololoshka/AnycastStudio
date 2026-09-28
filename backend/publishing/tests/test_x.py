import time
from unittest import mock

from django.utils import timezone

from config.wiring import container
from media.models import MediaAsset
from platforms.core.errors import FailureType
from platforms.core.publishing.confirmation import ConfirmationPoller
from platforms.core.publishing.pipeline import PublicationPipeline
from platforms.x.client import API_ROOT
from publishing.models import PublicationTarget
from social.models import SocialAccount

from .base import CONTENT, FakeResponse, PublishingTestCase

Status = PublicationTarget.Status

MEDIA_ID = "1880000000000000001"
POST_ID = "1990000000000000001"
POST_URL = f"https://x.com/i/web/status/{POST_ID}"
MEDIA_ROOT = f"{API_ROOT}/media/upload"


class XDouble:
    def __init__(self, states=None, post_answer=None):
        self.states = list(states or ["succeeded"])
        self.post_answer = post_answer or FakeResponse(201, {"data": {"id": POST_ID, "text": "A video"}})
        self.initialized: list[dict] = []
        self.received = 0
        self.finalized = 0
        self.status_calls = 0
        self.posts: list[dict] = []

    def next_state(self) -> str:
        return self.states.pop(0) if len(self.states) > 1 else self.states[0]

    def __call__(self, method, url, **kwargs):
        if url == f"{MEDIA_ROOT}/initialize":
            self.initialized.append(kwargs["json"])
            return FakeResponse(200, {"data": {"id": MEDIA_ID}})
        if url == f"{MEDIA_ROOT}/{MEDIA_ID}/append":
            self.received += len(kwargs["files"]["media"][1])
            return FakeResponse(200, {})
        if url == f"{MEDIA_ROOT}/{MEDIA_ID}/finalize":
            self.finalized += 1
            return FakeResponse(200, {"data": {"id": MEDIA_ID, "processing_info": {"state": "pending"}}})
        if url == MEDIA_ROOT and method == "GET":
            self.status_calls += 1
            state = self.next_state()
            error = {"error": {"name": "InvalidMedia", "message": "Unsupported codec"}} if state == "failed" else {}
            return FakeResponse(200, {"data": {"id": MEDIA_ID, "processing_info": {"state": state, **error}}})
        if url == f"{API_ROOT}/tweets":
            self.posts.append(kwargs["json"])
            return self.post_answer
        raise AssertionError(f"unexpected call to {method} {url}")


class XPublishingScenarios(PublishingTestCase):
    def setUp(self):
        super().setUp()
        self.account = SocialAccount.objects.create(
            user=self.user,
            platform="x",
            external_id="2244994945",
            display_name="a_creator",
            access_token="x.access",
            refresh_token="x.refresh",
            token_expires_at=timezone.now() + timezone.timedelta(hours=2),
        )
        MediaAsset.objects.filter(pk=self.asset.pk).update(duration_seconds=30)
        patcher = mock.patch("publishing.tasks.run_target.delay")
        patcher.start()
        self.addCleanup(patcher.stop)

    def given_x(self, **kwargs) -> XDouble:
        double = XDouble(**kwargs)
        self.http.side_effect = double
        return double

    def given_target(self, **settings) -> PublicationTarget:
        self.create_publication(targets=[{"platform": "x", "socialAccountId": self.account.pk, "settings": settings}])
        return self.only_target()

    def given_uploaded(self, **double) -> PublicationTarget:
        self.given_x(**double)
        target = self.given_target()
        container().pipeline.run(target.pk)
        target.refresh_from_db()
        return target

    def confirm_again(self, target: PublicationTarget):
        PublicationTarget.objects.filter(pk=target.pk).update(last_activity_at=timezone.now())
        return container().confirmations.confirm(target.pk)

    def test_an_upload_leaves_the_target_waiting_for_x(self):
        # Given: X accepts the video
        double = self.given_x()
        target = self.given_target()

        # When: the worker runs it
        result = container().pipeline.run(target.pk)

        # Then: the file went up, and nothing is posted until X has processed it
        target.refresh_from_db()
        self.assertEqual(result, Status.PROCESSING)
        self.assertEqual(target.uploaded_media_id, MEDIA_ID)
        self.assertEqual(double.received, len(CONTENT))
        self.assertEqual(double.finalized, 1)
        self.assertEqual(double.posts, [])

    def test_a_video_too_long_for_x_is_refused_before_any_call(self):
        # Given: a three-minute video
        MediaAsset.objects.filter(pk=self.asset.pk).update(duration_seconds=180)
        self.given_x()
        target = self.given_target()

        # When: the worker runs it
        container().pipeline.run(target.pk)

        # Then: it fails locally, and X was never asked
        target.refresh_from_db()
        self.assertEqual(target.status, Status.FAILED)
        self.assertEqual(target.error["type"], FailureType.VALIDATION)
        self.assertIn("videoTooLong", target.error["details"])
        self.http.assert_not_called()

    def test_text_longer_than_a_post_is_refused_before_any_call(self):
        self.given_x()
        self.create_publication(
            description="x" * 280,
            targets=[{"platform": "x", "socialAccountId": self.account.pk, "settings": {}}],
        )
        target = self.only_target()

        container().pipeline.run(target.pk)

        target.refresh_from_db()
        self.assertIn("captionTooLong", target.error["details"])
        self.http.assert_not_called()

    def test_a_processed_video_is_posted_and_completes_with_its_link(self):
        # Given: an uploaded video that X has finished processing
        target = self.given_uploaded(states=["succeeded"])
        PublicationTarget.objects.filter(pk=target.pk).update(
            settings={"replyAudience": "verified", "paidPartnership": True}
        )

        # When: the confirmation runs
        delay = container().confirmations.confirm(target.pk)

        # Then: one post, with the caption, the video and the chosen options
        target.refresh_from_db()
        double = self.http.side_effect
        self.assertIsNone(delay)
        self.assertEqual(target.status, Status.COMPLETED)
        self.assertEqual(target.published_url, POST_URL)
        self.assertEqual(
            double.posts,
            [
                {
                    "text": "A video\n\nAbout things\n\n#one #two",
                    "media": {"media_ids": [MEDIA_ID]},
                    "reply_settings": "verified",
                    "paid_partnership": True,
                }
            ],
        )

    def test_a_video_still_processing_is_not_posted_yet(self):
        # Given: X is still processing the video
        target = self.given_uploaded(states=["in_progress"])

        # When: the confirmation runs
        delay = container().confirmations.confirm(target.pk)

        # Then: it asks again later and posts nothing
        target.refresh_from_db()
        self.assertEqual(delay, ConfirmationPoller.POLL_DELAYS_SECONDS[1])
        self.assertEqual(target.status, Status.PROCESSING)
        self.assertEqual(self.http.side_effect.posts, [])

    def test_a_video_x_could_not_process_fails_with_its_reason(self):
        target = self.given_uploaded(states=["failed"])

        container().confirmations.confirm(target.pk)

        target.refresh_from_db()
        self.assertEqual(target.status, Status.FAILED)
        self.assertEqual((target.error["type"], target.error["message"]), (FailureType.FILE, "Unsupported codec"))
        self.assertEqual(self.http.side_effect.posts, [])

    def test_a_refused_post_fails_and_is_not_retried(self):
        # Given: X refuses the post, a decision that does not change on repetition
        refused = FakeResponse(403, {"detail": "You are not allowed to create a Tweet with duplicate content.", "status": 403})
        target = self.given_uploaded(post_answer=refused)

        # When: the confirmation runs
        delay = container().confirmations.confirm(target.pk)

        # Then: it fails with X's words, after one attempt
        target.refresh_from_db()
        self.assertIsNone(delay)
        self.assertEqual(target.status, Status.FAILED)
        self.assertEqual(target.error["type"], FailureType.AUTHORIZATION)
        self.assertIn("duplicate content", target.error["message"])
        self.assertEqual(len(self.http.side_effect.posts), 1)

    def test_a_post_x_did_not_answer_is_never_sent_again(self):
        # Given: the post request got no answer, so it may exist on X
        target = self.given_uploaded(post_answer=FakeResponse(503, {}))

        # When: the confirmation runs, and the person retries the failed target
        container().confirmations.confirm(target.pk)
        target.refresh_from_db()
        failed = (target.status, target.error["message"])
        PublicationTarget.objects.filter(pk=target.pk).update(status=Status.QUEUED)
        container().pipeline.run(target.pk)
        self.confirm_again(target)

        # Then: both times it fails asking the person to check X, and only one post was ever sent
        target.refresh_from_db()
        self.assertEqual(failed[0], Status.FAILED)
        self.assertIn("check X", failed[1])
        self.assertEqual(target.status, Status.FAILED)
        self.assertIn("check X", target.error["message"])
        self.assertEqual(len(self.http.side_effect.posts), 1)

    def test_a_rejected_token_is_refreshed_and_the_post_is_sent_once(self):
        # Given: the token is rejected at the post, and X issues a fresh one
        target = self.given_uploaded()
        double = self.http.side_effect
        answers = [FakeResponse(401, {"title": "Unauthorized"}), FakeResponse(201, {"data": {"id": POST_ID}})]
        tokens = FakeResponse(200, {"access_token": "x.fresh", "refresh_token": "x.rotated", "expires_in": 7200})

        def route(method, url, **kwargs):
            if url.endswith("/oauth2/token"):
                return tokens
            if url == f"{API_ROOT}/tweets":
                double.posts.append(kwargs["json"])
                return answers.pop(0)
            return double(method, url, **kwargs)

        self.http.side_effect = route

        # When: the confirmation runs
        container().confirmations.confirm(target.pk)

        # Then: the refused attempt did not count as maybe posted, and the second completed it
        target.refresh_from_db()
        self.account.refresh_from_db()
        self.assertEqual(target.status, Status.COMPLETED)
        self.assertEqual(target.published_url, POST_URL)
        self.assertEqual(len(double.posts), 2)
        self.assertEqual(self.account.refresh_token, "x.rotated")

    def test_a_revoked_connection_asks_for_reconnection(self):
        target = self.given_uploaded()
        self.http.side_effect = [
            FakeResponse(401, {"title": "Unauthorized"}),
            FakeResponse(400, {"error": "invalid_request", "error_description": "Value passed for the token was invalid."}),
        ]

        container().confirmations.confirm(target.pk)

        target.refresh_from_db()
        self.account.refresh_from_db()
        self.assertEqual(target.error["type"], FailureType.AUTHENTICATION)
        self.assertEqual(self.account.status, SocialAccount.Status.NEEDS_REAUTH)

    def test_a_video_never_processed_fails_after_the_deadline(self):
        target = self.given_uploaded(states=["in_progress"])
        started = time.time() - ConfirmationPoller.CONFIRM_WITHIN_SECONDS - 1
        PublicationTarget.objects.filter(pk=target.pk).update(resume_state={"confirming_since": started, "polls": 9})

        delay = container().confirmations.confirm(target.pk)

        target.refresh_from_db()
        self.assertIsNone(delay)
        self.assertEqual((target.status, target.error["type"]), (Status.FAILED, FailureType.PLATFORM))

    def test_a_confirmation_delivered_again_after_completion_does_nothing(self):
        target = self.given_uploaded()
        container().confirmations.confirm(target.pk)
        calls = self.http.call_count

        delay = container().confirmations.confirm(target.pk)

        target.refresh_from_db()
        self.assertIsNone(delay)
        self.assertEqual(self.http.call_count, calls)
        self.assertEqual(target.status, Status.COMPLETED)

    def test_the_claim_for_abandoned_work_leaves_a_target_being_confirmed_alone(self):
        target = self.given_uploaded()
        PublicationTarget.objects.filter(pk=target.pk).update(
            last_activity_at=timezone.now() - PublicationPipeline.ABANDONED_AFTER * 2
        )

        self.assertIsNone(container().pipeline.claim(target.pk))

    def test_a_worker_killed_mid_upload_resumes_the_same_media(self):
        # Given: a target whose upload stopped after the first segment
        double = self.given_x(states=["in_progress"])
        target = self.given_target()
        PublicationTarget.objects.filter(pk=target.pk).update(
            status=Status.UPLOADING,
            last_activity_at=timezone.now() - PublicationPipeline.ABANDONED_AFTER * 2,
            resume_state={"media_id": MEDIA_ID, "segment_bytes": 1024, "next_segment": 1, "created_at": time.time() - 60},
        )

        # When: the worker picks it up again
        container().pipeline.run(target.pk)

        # Then: no new upload, only the rest of the file
        target.refresh_from_db()
        self.assertEqual(target.status, Status.PROCESSING)
        self.assertEqual(double.initialized, [])
        self.assertEqual(double.received, len(CONTENT) - 1024)

    def test_capabilities_are_served_for_x(self):
        body = self.body(self.client.get("/api/platforms"))

        x = body["platforms"]["x"]
        self.assertEqual(x["scheduling"], "deferredUpload")
        self.assertEqual(x["maxFileSize"], 512 * 1024**2)
        self.assertEqual(x["supportedMimeTypes"], ["video/mp4", "video/quicktime"])
