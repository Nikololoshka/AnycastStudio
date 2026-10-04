from unittest import mock

from django.utils import timezone

from accounts.models import User
from media.models import MediaAsset
from publishing.models import Publication, PublicationTarget
from social.models import SocialAccount

from .base import PublishingTestCase

Status = PublicationTarget.Status


class CreateScenarios(PublishingTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("services.tasks.run_target.delay")
        self.dispatch = patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_publication_is_created_and_handed_to_the_worker(self):
        response = self.create_publication()

        self.assertEqual(response.status_code, 200)
        body = self.body(response)["publication"]
        self.assertEqual(body["title"], "A video")
        self.assertEqual(body["targets"][0]["status"], Status.QUEUED)
        self.assertTrue(body["isActive"])
        self.dispatch.assert_called_once()

    def test_the_platform_settings_are_kept_as_sent(self):
        self.create_publication()

        self.assertEqual(self.only_target().settings, {"privacyStatus": "public"})

    def test_a_scheduled_publication_records_when(self):
        when = timezone.now() + timezone.timedelta(hours=2)

        self.create_publication(publishAt=when.isoformat())

        self.assertIsNotNone(self.only_publication().publish_at)

    def test_an_unparseable_time_is_refused(self):
        response = self.create_publication(publishAt="tomorrow-ish")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Publication.objects.exists())

    def test_a_time_in_the_past_is_refused_before_any_quota_is_spent(self):
        # Given: a schedule that has already passed
        when = timezone.now() - timezone.timedelta(minutes=5)

        # When: it is sent
        response = self.create_publication(publishAt=when.isoformat())

        # Then: it is refused here, not by YouTube after the upload
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.body(response)["errors"][0]["field"], "publishAt")
        self.assertFalse(Publication.objects.exists())

    def test_a_time_without_a_time_zone_is_refused(self):
        response = self.create_publication(publishAt="2030-01-01T10:00:00")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.body(response)["errors"][0]["field"], "publishAt")

    def test_two_targets_on_one_platform_are_refused(self):
        # Given: the same platform asked for twice
        target = {"platform": "youtube", "socialAccountId": self.account.pk}

        # When: it is sent
        response = self.create_publication(targets=[target, target])

        # Then: it is refused as invalid instead of failing on the database
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.body(response)["errors"][0]["field"], "targets")
        self.assertFalse(Publication.objects.exists())

    def test_a_publication_without_a_title_is_refused(self):
        response = self.create_publication(title="")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.body(response)["errors"][0]["field"], "title")

    def test_another_persons_media_cannot_be_published(self):
        # Given: a file belonging to somebody else
        other = User.objects.create_user("other@example.com", "another-password-99")
        theirs = MediaAsset.objects.create(
            user=other,
            filename="theirs.mp4",
            mime_type="video/mp4",
            size_bytes=10,
            storage_path="x",
            status=MediaAsset.Status.READY,
        )

        response = self.create_publication(mediaAssetId=theirs.pk)

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Publication.objects.exists())

    def test_another_persons_account_cannot_be_published_to(self):
        other = User.objects.create_user("other@example.com", "another-password-99")
        theirs = SocialAccount.objects.create(
            user=other, platform="youtube", external_id="UC_other", access_token="t"
        )

        response = self.create_publication(
            targets=[{"platform": "youtube", "socialAccountId": theirs.pk, "settings": {}}]
        )

        self.assertEqual(response.status_code, 404)

    def test_a_disconnected_account_cannot_be_published_to(self):
        SocialAccount.objects.filter(pk=self.account.pk).update(status=SocialAccount.Status.REVOKED)

        response = self.create_publication()

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Publication.objects.exists())

    def test_an_account_that_needs_reconnecting_is_refused_with_a_reason(self):
        SocialAccount.objects.filter(pk=self.account.pk).update(
            status=SocialAccount.Status.NEEDS_REAUTH
        )

        response = self.create_publication()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.body(response)["message"], "account_needs_reauth")

    def test_the_daily_limit_is_enforced_with_a_reason(self):
        # Given: a daily limit of one. The YouTube quota is per project, so this has
        # to refuse before Google does, or the person meets a 403 they cannot act on
        self.user.max_publications_per_day = 1
        self.user.save()

        self.create_publication()
        second = self.create_publication()

        self.assertEqual(self.body(second)["status"], "quota_exceeded")
        self.assertEqual(Publication.objects.count(), 1)

    def test_signing_in_is_required(self):
        self.client.logout()

        self.assertEqual(self.create_publication().status_code, 401)
