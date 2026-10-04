import time
from unittest import mock

from django.utils import timezone

from media.models import MediaAsset
from platforms.core import PlatformFailure
from platforms.instagram.core import InstagramEndpoints
from platforms.tests.fakes.http import FakeAnswer
from publishing.models import PublicationTarget
from services import tasks
from services.usecases.publications import ConfirmationPoller, StaleTargetSweeper
from social.models import SocialAccount

from .base import CONTENT, PublishingTestCase

GRAPH_ROOT = InstagramEndpoints.GRAPH_ROOT
RUPLOAD_ROOT = InstagramEndpoints.RUPLOAD_ROOT

Status = PublicationTarget.Status

IG_USER_ID = "17841400000000001"
CONTAINER_ID = "17900000000000001"
MEDIA_ID = "18000000000000001"
PERMALINK = "https://www.instagram.com/reel/abc/"


class InstagramDouble:
    def __init__(self, size: int, statuses=None, publish_answer=None):
        self.size = size
        self.statuses = list(statuses or ["FINISHED"])
        self.publish_answer = publish_answer or FakeAnswer(200, {"id": MEDIA_ID})
        self.containers: list[dict] = []
        self.received = 0
        self.status_calls = 0
        self.publishes = 0

    def next_status(self) -> str:
        return self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]

    def __call__(self, method, url, **kwargs):
        if url == f"{GRAPH_ROOT}/{IG_USER_ID}/media":
            self.containers.append(kwargs["data"])
            return FakeAnswer(200, {"id": CONTAINER_ID})
        if url.startswith(f"{RUPLOAD_ROOT}/"):
            self.received += len(kwargs["data"])
            return FakeAnswer(200, {"success": True})
        if url == f"{GRAPH_ROOT}/{CONTAINER_ID}":
            self.status_calls += 1
            return FakeAnswer(200, {"status_code": self.next_status(), "status": "Error: 2207026"})
        if url == f"{GRAPH_ROOT}/{IG_USER_ID}/media_publish":
            self.publishes += 1
            return self.publish_answer
        if url == f"{GRAPH_ROOT}/{MEDIA_ID}":
            return FakeAnswer(200, {"permalink": PERMALINK})
        raise AssertionError(f"unexpected call to {method} {url}")


class InstagramPublishingScenarios(PublishingTestCase):
    def setUp(self):
        super().setUp()
        self.account = SocialAccount.objects.create(
            user=self.user,
            platform="instagram",
            external_id=IG_USER_ID,
            display_name="a.creator",
            access_token="EAAG.page-token",
        )
        MediaAsset.objects.filter(pk=self.asset.pk).update(duration_seconds=30)
        patcher = mock.patch("services.tasks.run_target.delay")
        patcher.start()
        self.addCleanup(patcher.stop)

    def given_instagram(self, **kwargs) -> InstagramDouble:
        double = InstagramDouble(size=len(CONTENT), **kwargs)
        self.http.responder = double
        return double

    def given_target(self, **settings) -> PublicationTarget:
        self.create_publication(
            targets=[{"platform": "instagram", "socialAccountId": self.account.pk, "settings": settings}]
        )
        return self.only_target()

    def given_uploaded(self, **double) -> PublicationTarget:
        self.given_instagram(**double)
        target = self.given_target()
        self.run_target(target.pk)
        target.refresh_from_db()
        return target

    def test_an_upload_leaves_the_target_waiting_for_instagram(self):
        # Given: Instagram accepts the reel
        double = self.given_instagram()
        target = self.given_target(shareToFeed=False, coverFrameSeconds=2)

        # When: the worker runs it
        result = self.run_target(target.pk)

        # Then: the file went up, and nothing is published until Instagram has processed it
        target.refresh_from_db()
        self.assertEqual(result, Status.PROCESSING)
        self.assertEqual(target.status, Status.PROCESSING)
        self.assertEqual(target.uploaded_media_id, CONTAINER_ID)
        self.assertEqual(double.received, len(CONTENT))
        self.assertEqual(double.publishes, 0)
        container = double.containers[0]
        self.assertEqual(container["caption"], "A video\n\nAbout things\n\n#one #two")
        self.assertEqual((container["share_to_feed"], container["thumb_offset"]), ("false", "2000"))

    def test_a_video_too_short_for_a_reel_is_refused_before_any_call(self):
        # Given: a two-second video
        MediaAsset.objects.filter(pk=self.asset.pk).update(duration_seconds=2)
        self.given_instagram()
        target = self.given_target()

        # When: the worker runs it
        self.run_target(target.pk)

        # Then: it fails locally, and Instagram was never asked
        target.refresh_from_db()
        self.assertEqual(target.status, Status.FAILED)
        self.assertEqual(target.error["failure"], PlatformFailure.INVALID)
        self.assertIn("videoTooShort", target.error["details"])
        self.assertEqual(self.http.sent, [])

    def test_a_processed_reel_is_published_and_completes_with_its_link(self):
        # Given: an uploaded reel that Instagram has finished processing
        target = self.given_uploaded(statuses=["FINISHED"])

        # When: the confirmation runs
        delay = self.confirm_target(target.pk)

        # Then: it was published once, with the post's address
        target.refresh_from_db()
        self.assertIsNone(delay)
        self.assertEqual(target.status, Status.COMPLETED)
        self.assertEqual(target.published_url, PERMALINK)
        self.assertEqual(self.http.responder.publishes, 1)

    def test_a_reel_still_processing_is_not_published_yet(self):
        # Given: Instagram is still processing the video
        target = self.given_uploaded(statuses=["IN_PROGRESS"])

        # When: the confirmation runs
        delay = self.confirm_target(target.pk)

        # Then: it asks again later and publishes nothing
        target.refresh_from_db()
        self.assertEqual(delay, ConfirmationPoller.POLL_DELAYS_SECONDS[1])
        self.assertEqual(target.status, Status.PROCESSING)
        self.assertEqual(self.http.responder.publishes, 0)

    def test_a_reel_instagram_could_not_process_fails_with_its_reason(self):
        target = self.given_uploaded(statuses=["ERROR"])

        self.confirm_target(target.pk)

        target.refresh_from_db()
        self.assertEqual(target.status, Status.FAILED)
        self.assertEqual(target.error["failure"], PlatformFailure.FILE_REJECTED)
        self.assertEqual(target.error["details"], "Error: 2207026")

    def test_an_expired_container_fails(self):
        target = self.given_uploaded(statuses=["EXPIRED"])

        self.confirm_target(target.pk)

        target.refresh_from_db()
        self.assertEqual((target.status, target.error["details"]), (Status.FAILED, "EXPIRED"))

    def test_a_lost_answer_to_publish_is_asked_about_again_rather_than_published_twice(self):
        # Given: the publish call is lost, but Instagram published the reel anyway
        target = self.given_uploaded(statuses=["FINISHED", "PUBLISHED"], publish_answer=FakeAnswer(503, {}))

        # When: two confirmations run
        first = self.confirm_target(target.pk)
        PublicationTarget.objects.filter(pk=target.pk).update(last_activity_at=timezone.now())
        second = self.confirm_target(target.pk)

        # Then: the second sees it published, and publish was sent only once
        target.refresh_from_db()
        self.assertEqual(first, ConfirmationPoller.POLL_DELAYS_SECONDS[1])
        self.assertIsNone(second)
        self.assertEqual(target.status, Status.COMPLETED)
        self.assertEqual(self.http.responder.publishes, 1)

    def test_a_refused_publish_fails_and_is_not_retried(self):
        # Given: Instagram refuses to publish, a decision that does not change on repetition
        refused = FakeAnswer(400, {"error": {"message": "Daily limit reached", "code": 9, "error_subcode": 2207042}})
        target = self.given_uploaded(publish_answer=refused)

        # When: the confirmation runs
        delay = self.confirm_target(target.pk)

        # Then: it fails with Instagram's words
        target.refresh_from_db()
        self.assertIsNone(delay)
        self.assertEqual(target.status, Status.FAILED)
        self.assertEqual(target.error["failure"], PlatformFailure.REFUSED)
        self.assertIn("Daily limit reached", target.error["message"])
        self.assertEqual(self.http.responder.publishes, 1)

    def test_a_reel_never_processed_fails_after_the_deadline(self):
        target = self.given_uploaded(statuses=["IN_PROGRESS"])
        started = time.time() - ConfirmationPoller.CONFIRM_WITHIN.total_seconds() - 1
        PublicationTarget.objects.filter(pk=target.pk).update(confirmation_state={"confirming_since": started, "polls": 9})

        delay = self.confirm_target(target.pk)

        target.refresh_from_db()
        self.assertIsNone(delay)
        self.assertEqual((target.status, target.error["failure"]), (Status.FAILED, PlatformFailure.UNCONFIRMED))

    def test_a_rejected_token_asks_for_reconnection(self):
        # Given: the person revoked the app on Facebook; a Page token cannot be refreshed
        target = self.given_uploaded()
        self.given_answers(FakeAnswer(400, {"error": {"message": "Session invalidated", "code": 190}}))

        # When: the confirmation runs
        self.confirm_target(target.pk)

        # Then: the target fails for authentication, and the account asks to be reconnected
        target.refresh_from_db()
        self.account.refresh_from_db()
        self.assertEqual(target.error["failure"], PlatformFailure.GRANT_REVOKED)
        self.assertEqual(self.account.status, SocialAccount.Status.NEEDS_REAUTH)

    def test_a_confirmation_delivered_again_after_completion_does_nothing(self):
        target = self.given_uploaded()
        self.confirm_target(target.pk)
        calls = len(self.http.sent)

        delay = self.confirm_target(target.pk)

        target.refresh_from_db()
        self.assertIsNone(delay)
        self.assertEqual(len(self.http.sent), calls)
        self.assertEqual(target.status, Status.COMPLETED)

    def test_the_sweep_for_abandoned_work_leaves_a_target_being_confirmed_alone(self):
        target = self.given_uploaded()
        PublicationTarget.objects.filter(pk=target.pk).update(
            last_activity_at=timezone.now() - StaleTargetSweeper.ABANDONED_AFTER * 2
        )

        self.assertEqual(tasks.sweep_abandoned_targets(), 0)
        target.refresh_from_db()
        self.assertEqual(target.status, Status.PROCESSING)

    def test_capabilities_are_served_for_instagram(self):
        body = self.body(self.client.get("/api/platforms"))

        instagram = body["platforms"]["instagram"]
        self.assertEqual(instagram["scheduling"], "deferredUpload")
        self.assertEqual(instagram["supportedMimeTypes"], ["video/mp4", "video/quicktime"])
