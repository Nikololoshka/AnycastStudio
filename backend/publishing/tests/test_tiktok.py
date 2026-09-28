import time
from unittest import mock

from django.utils import timezone

from config.wiring import container
from media.models import MediaAsset
from platforms.core.errors import FailureType
from platforms.core.publishing.confirmation import ConfirmationPoller
from platforms.core.publishing.dispatcher import DeferredDispatcher
from platforms.core.publishing.pipeline import PublicationPipeline
from publishing import tasks
from publishing.models import PublicationTarget
from social.models import SocialAccount

from .base import CONTENT, FakeResponse, PublishingTestCase

Status = PublicationTarget.Status

PUBLISH_ID = "v_pub_file~v2-1.123"
UPLOAD_URL = "https://open-upload.tiktokapis.com/video/?upload_id=1"
PRIVATE_ONLY = ["SELF_ONLY", "FOLLOWER_OF_CREATOR"]


def envelope(data: dict) -> FakeResponse:
    return FakeResponse(200, {"data": data, "error": {"code": "ok", "message": "", "log_id": "log"}})


class TikTokDouble:
    def __init__(self, size: int, privacy_options=None, max_duration=600, statuses=None, comment_disabled=False):
        self.size = size
        self.privacy_options = privacy_options or PRIVATE_ONLY
        self.max_duration = max_duration
        self.comment_disabled = comment_disabled
        self.statuses = list(statuses or [{"status": "PUBLISH_COMPLETE"}])
        self.inits: list[dict] = []
        self.received = 0
        self.status_calls = 0

    def __call__(self, method, url, **kwargs):
        if url.endswith("/creator_info/query/"):
            return envelope(
                {
                    "creator_username": "a.creator",
                    "creator_nickname": "A Creator",
                    "privacy_level_options": self.privacy_options,
                    "comment_disabled": self.comment_disabled,
                    "duet_disabled": False,
                    "stitch_disabled": False,
                    "max_video_post_duration_sec": self.max_duration,
                }
            )
        if url.endswith("/post/publish/video/init/"):
            self.inits.append(kwargs["json"])
            return envelope({"publish_id": PUBLISH_ID, "upload_url": UPLOAD_URL})
        if url == UPLOAD_URL:
            self.received += len(kwargs["data"])
            return FakeResponse(201 if self.received >= self.size else 206)
        if url.endswith("/post/publish/status/fetch/"):
            self.status_calls += 1
            current = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
            return envelope(current)
        raise AssertionError(f"unexpected call to {url}")


class TikTokPublishingScenarios(PublishingTestCase):
    def setUp(self):
        super().setUp()
        self.account = SocialAccount.objects.create(
            user=self.user,
            platform="tiktok",
            external_id="open-id-1",
            display_name="A Creator",
            access_token="act.token",
            refresh_token="rft.token",
            token_expires_at=timezone.now() + timezone.timedelta(hours=12),
        )
        MediaAsset.objects.filter(pk=self.asset.pk).update(duration_seconds=30)
        patcher = mock.patch("publishing.tasks.run_target.delay")
        self.dispatch = patcher.start()
        self.addCleanup(patcher.stop)

    def given_tiktok(self, **kwargs) -> TikTokDouble:
        double = TikTokDouble(size=len(CONTENT), **kwargs)
        self.http.side_effect = double
        return double

    def given_target(self, **settings) -> PublicationTarget:
        self.create_publication(
            targets=[
                {
                    "platform": "tiktok",
                    "socialAccountId": self.account.pk,
                    "settings": {"privacyLevel": "SELF_ONLY", **settings},
                }
            ]
        )
        return self.only_target()

    def given_uploaded(self, **double) -> PublicationTarget:
        self.given_tiktok(**double)
        target = self.given_target()
        container().pipeline.run(target.pk)
        target.refresh_from_db()
        return target

    def test_an_upload_leaves_the_target_waiting_for_tiktok(self):
        # Given: TikTok accepts the post
        double = self.given_tiktok()
        target = self.given_target(disableDuet=True)

        # When: the worker runs it
        result = container().pipeline.run(target.pk)

        # Then: the file went up, and the target waits for TikTok to confirm rather than claiming success
        target.refresh_from_db()
        self.assertEqual(result, Status.PROCESSING)
        self.assertEqual(target.status, Status.PROCESSING)
        self.assertEqual(target.uploaded_media_id, PUBLISH_ID)
        self.assertIsNone(target.finished_at)
        self.assertEqual(double.received, len(CONTENT))
        post_info = double.inits[0]["post_info"]
        self.assertEqual(post_info["title"], "A video\n\nAbout things\n\n#one #two")
        self.assertTrue(post_info["disable_duet"])

    def test_the_worker_schedules_the_first_confirmation(self):
        self.given_tiktok()
        target = self.given_target()

        with mock.patch("publishing.tasks.confirm_target.apply_async") as confirm:
            tasks.run_target(target.pk)

        confirm.assert_called_once_with((target.pk,), countdown=ConfirmationPoller.POLL_DELAYS_SECONDS[0])

    def test_a_setting_the_creator_turned_off_stays_off(self):
        # Given: the creator disabled comments in the TikTok app
        double = self.given_tiktok(comment_disabled=True)
        target = self.given_target(disableComment=False)

        # When: the post is uploaded
        container().pipeline.run(target.pk)

        # Then: comments are disabled on the post too
        self.assertTrue(double.inits[0]["post_info"]["disable_comment"])

    def test_a_missing_privacy_level_is_refused_before_any_call(self):
        # Given: no privacy level chosen
        self.given_tiktok()
        target = self.given_target(privacyLevel=None)

        # When: the worker runs it
        container().pipeline.run(target.pk)

        # Then: it fails locally, and TikTok was never asked
        target.refresh_from_db()
        self.assertEqual(target.status, Status.FAILED)
        self.assertEqual(target.error["type"], FailureType.VALIDATION)
        self.assertIn("privacyRequired", target.error["details"])
        self.http.assert_not_called()

    def test_a_privacy_level_the_creator_does_not_offer_is_refused_before_uploading(self):
        # Given: an unaudited app, which can only post privately
        double = self.given_tiktok(privacy_options=["SELF_ONLY"])
        target = self.given_target(privacyLevel="PUBLIC_TO_EVERYONE")

        # When: the worker runs it
        container().pipeline.run(target.pk)

        # Then: nothing was uploaded
        target.refresh_from_db()
        self.assertEqual(target.status, Status.FAILED)
        self.assertIn("privacyNotOffered", target.error["details"])
        self.assertEqual(double.inits, [])

    def test_a_video_longer_than_the_creator_may_post_is_refused_before_uploading(self):
        double = self.given_tiktok(max_duration=10)
        target = self.given_target()

        container().pipeline.run(target.pk)

        target.refresh_from_db()
        self.assertIn("videoTooLong", target.error["details"])
        self.assertEqual(double.inits, [])

    def test_a_confirmed_post_completes_with_its_link(self):
        # Given: an uploaded post that TikTok has published publicly
        target = self.given_uploaded(
            statuses=[{"status": "PUBLISH_COMPLETE", "publicaly_available_post_id": [7123]}]
        )

        # When: the confirmation runs
        delay = container().confirmations.confirm(target.pk)

        # Then: the target is done, with the post's address
        target.refresh_from_db()
        self.assertIsNone(delay)
        self.assertEqual(target.status, Status.COMPLETED)
        self.assertEqual(target.published_url, "https://www.tiktok.com/@a.creator/video/7123")
        self.assertIsNotNone(target.finished_at)

    def test_a_private_post_completes_without_a_link(self):
        target = self.given_uploaded(statuses=[{"status": "PUBLISH_COMPLETE"}])

        container().confirmations.confirm(target.pk)

        target.refresh_from_db()
        self.assertEqual(target.status, Status.COMPLETED)
        self.assertEqual(target.published_url, "")

    def test_a_post_still_processing_is_asked_about_again_later(self):
        # Given: TikTok is still processing the video
        target = self.given_uploaded(statuses=[{"status": "PROCESSING_UPLOAD"}])

        # When: two confirmations run
        first = container().confirmations.confirm(target.pk)
        PublicationTarget.objects.filter(pk=target.pk).update(last_activity_at=timezone.now())
        second = container().confirmations.confirm(target.pk)

        # Then: each asks for the next, longer wait
        self.assertEqual((first, second), ConfirmationPoller.POLL_DELAYS_SECONDS[1:3])
        target.refresh_from_db()
        self.assertEqual(target.status, Status.PROCESSING)

    def test_a_refused_post_fails_with_tiktoks_reason(self):
        # Given: TikTok rejects the video after processing it
        target = self.given_uploaded(statuses=[{"status": "FAILED", "fail_reason": "file_format_check_failed"}])

        # When: the confirmation runs
        container().confirmations.confirm(target.pk)

        # Then: the reason reaches the person
        target.refresh_from_db()
        self.assertEqual(target.status, Status.FAILED)
        self.assertEqual(target.error["type"], FailureType.FILE)
        self.assertEqual(target.error["details"], "file_format_check_failed")

    def test_a_post_that_is_never_confirmed_fails_after_the_deadline(self):
        # Given: TikTok has been processing for longer than we wait
        target = self.given_uploaded(statuses=[{"status": "PROCESSING_UPLOAD"}])
        started = time.time() - ConfirmationPoller.CONFIRM_WITHIN_SECONDS - 1
        PublicationTarget.objects.filter(pk=target.pk).update(resume_state={"confirming_since": started, "polls": 9})

        # When: the confirmation runs
        delay = container().confirmations.confirm(target.pk)

        # Then: the person is told to check TikTok, and it is not retried
        target.refresh_from_db()
        self.assertIsNone(delay)
        self.assertEqual(target.status, Status.FAILED)
        self.assertEqual(target.error["type"], FailureType.PLATFORM)

    def test_an_expired_token_during_confirmation_is_refreshed_once(self):
        # Given: the token is refused while polling
        target = self.given_uploaded()
        self.http.side_effect = [
            FakeResponse(401, {"error": {"code": "access_token_invalid", "message": "expired"}}),
            envelope({"status": "PUBLISH_COMPLETE"}),
        ]

        # When: the confirmation runs
        with mock.patch(
            "social.tokens.DjangoAccessTokens.refresh", return_value="act.fresh"
        ) as refresh:
            container().confirmations.confirm(target.pk)

        # Then: it refreshed and completed
        refresh.assert_called_once()
        target.refresh_from_db()
        self.assertEqual(target.status, Status.COMPLETED)

    def test_a_confirmation_delivered_again_after_completion_does_nothing(self):
        # Given: a post already confirmed
        target = self.given_uploaded()
        container().confirmations.confirm(target.pk)
        calls = self.http.side_effect.status_calls

        # When: the same confirmation message is delivered again
        delay = container().confirmations.confirm(target.pk)

        # Then: TikTok is not asked again and the target stays completed
        target.refresh_from_db()
        self.assertIsNone(delay)
        self.assertEqual(self.http.side_effect.status_calls, calls)
        self.assertEqual(target.status, Status.COMPLETED)

    def test_a_target_being_confirmed_cannot_be_cancelled(self):
        # Given: the video is already with TikTok
        target = self.given_uploaded()

        # When: the person asks to cancel
        response = self.client.post(f"/api/targets/{target.pk}/cancel")

        # Then: it is refused, since TikTok cannot take it back
        self.assertEqual(response.status_code, 409)

    def test_the_claim_for_abandoned_work_leaves_a_target_being_confirmed_alone(self):
        # Given: a target waiting for TikTok, silent for longer than the abandonment window
        target = self.given_uploaded()
        PublicationTarget.objects.filter(pk=target.pk).update(
            last_activity_at=timezone.now() - PublicationPipeline.ABANDONED_AFTER * 2
        )

        # When / Then: the upload claim does not take it, so nothing is uploaded twice
        self.assertIsNone(container().pipeline.claim(target.pk))

    def test_the_sweep_resumes_a_confirmation_whose_chain_was_lost(self):
        # Given: a target nobody has asked about for too long
        target = self.given_uploaded()
        PublicationTarget.objects.filter(pk=target.pk).update(
            last_activity_at=timezone.now() - DeferredDispatcher.CONFIRMATION_STALLED_AFTER * 2
        )

        # When: the sweep runs twice
        with mock.patch("publishing.tasks.confirm_target.delay") as confirm:
            tasks.dispatch_due_targets()
            tasks.dispatch_due_targets()

        # Then: the confirmation was resumed once
        confirm.assert_called_once_with(target.pk)

    def test_a_scheduled_tiktok_post_waits_for_its_time(self):
        # Given: TikTok cannot schedule, so the upload itself must wait
        when = timezone.now() + timezone.timedelta(hours=2)

        # When: a scheduled TikTok publication is created
        self.create_publication(
            publishAt=when.isoformat(),
            targets=[{"platform": "tiktok", "socialAccountId": self.account.pk, "settings": {"privacyLevel": "SELF_ONLY"}}],
        )

        # Then: nothing is handed to the worker yet
        self.dispatch.assert_not_called()

    def test_a_revoked_authorisation_asks_for_reconnection(self):
        target = self.given_uploaded(statuses=[{"status": "FAILED", "fail_reason": "auth_removed"}])

        container().confirmations.confirm(target.pk)

        target.refresh_from_db()
        self.assertEqual(target.error["type"], FailureType.AUTHENTICATION)

    def test_capabilities_are_served_for_tiktok(self):
        body = self.body(self.client.get("/api/platforms"))

        self.assertEqual(body["platforms"]["tiktok"]["scheduling"], "deferredUpload")

    def test_only_the_platforms_without_native_scheduling_wait_for_the_publish_time(self):
        self.assertEqual(container().catalog.deferring_upload(), ("tiktok", "instagram", "x"))
