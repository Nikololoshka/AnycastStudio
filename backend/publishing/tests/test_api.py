"""Creating and steering publications through the API, as Given / When / Then."""

import json
from unittest import mock

from django.utils import timezone

from accounts.models import User
from media.models import MediaAsset
from publishing.models import Publication, PublicationTarget
from publishing.tests.base import CREATE_URL, LIST_URL, PublishingTestCase
from social.models import SocialAccount

Status = PublicationTarget.Status


class CreateScenarios(PublishingTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("publishing.tasks.run_target.delay")
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

    def test_an_account_that_needs_reconnecting_is_refused_with_a_reason(self):
        SocialAccount.objects.filter(pk=self.account.pk).update(
            status=SocialAccount.Status.NEEDS_REAUTH
        )

        response = self.create_publication()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.body(response)["message"], "account_needs_reauth")

    def test_the_daily_limit_is_enforced_with_a_reason(self):
        # The YouTube quota is per project, so this has to refuse before Google
        # does, otherwise the person meets a 403 they cannot act on.
        self.user.max_publications_per_day = 1
        self.user.save()

        self.create_publication()
        second = self.create_publication()

        self.assertEqual(self.body(second)["status"], "quota_exceeded")
        self.assertEqual(Publication.objects.count(), 1)

    def test_signing_in_is_required(self):
        self.client.logout()

        self.assertEqual(self.create_publication().status_code, 401)


class ListScenarios(PublishingTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("publishing.tasks.run_target.delay")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_publications_are_listed_newest_first(self):
        self.create_publication(title="First")
        self.asset = self.given_uploaded_asset()
        self.create_publication(title="Second")

        rows = self.body(self.client.get(LIST_URL))["publications"]

        self.assertEqual([row["title"] for row in rows], ["Second", "First"])

    def test_a_single_publication_reports_its_targets(self):
        publication = self.body(self.create_publication())["publication"]

        body = self.body(self.client.get(f"{LIST_URL}/{publication['id']}"))

        self.assertEqual(len(body["publication"]["targets"]), 1)

    def test_a_finished_publication_stops_being_active(self):
        # Given: a publication whose only target completed. The browser polls
        # while isActive is true, so this is what makes it stop.
        publication = self.body(self.create_publication())["publication"]
        PublicationTarget.objects.update(status=Status.COMPLETED)

        body = self.body(self.client.get(f"{LIST_URL}/{publication['id']}"))

        self.assertFalse(body["publication"]["isActive"])

    def test_another_persons_publication_is_not_found(self):
        publication = self.body(self.create_publication())["publication"]
        other = User.objects.create_user("other@example.com", "another-password-99")
        self.client.force_login(other)

        response = self.client.get(f"{LIST_URL}/{publication['id']}")

        self.assertEqual(response.status_code, 404)

    def test_no_token_appears_in_a_publication(self):
        self.create_publication()

        content = self.client.get(LIST_URL).content.decode()

        self.assertNotIn("ya29.token", content)
        self.assertNotIn("1//refresh", content)


class CancelAndRetryScenarios(PublishingTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("publishing.tasks.run_target.delay")
        self.dispatch = patcher.start()
        self.addCleanup(patcher.stop)
        self.create_publication()
        self.target = self.only_target()

    def url(self, action: str) -> str:
        return f"/api/targets/{self.target.pk}/{action}"

    def test_cancelling_a_queued_target_stops_it_immediately(self):
        response = self.client.post(self.url("cancel"))

        self.assertEqual(response.status_code, 200)
        self.target.refresh_from_db()
        self.assertEqual(self.target.status, Status.CANCELLED)

    def test_cancelling_a_running_target_raises_the_flag_the_worker_watches(self):
        PublicationTarget.objects.filter(pk=self.target.pk).update(status=Status.UPLOADING)

        self.client.post(self.url("cancel"))

        self.target.refresh_from_db()
        self.assertTrue(self.target.cancel_requested)
        self.assertEqual(self.target.status, Status.UPLOADING)

    def test_cancelling_a_finished_target_is_refused(self):
        PublicationTarget.objects.filter(pk=self.target.pk).update(status=Status.COMPLETED)

        response = self.client.post(self.url("cancel"))

        self.assertEqual(response.status_code, 409)

    def test_retrying_a_failed_target_queues_it_again(self):
        PublicationTarget.objects.filter(pk=self.target.pk).update(
            status=Status.FAILED, error={"type": "network", "message": "lost"}
        )
        self.dispatch.reset_mock()

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url("retry"))

        self.assertEqual(response.status_code, 200)
        self.target.refresh_from_db()
        self.assertEqual(self.target.status, Status.QUEUED)
        self.assertIsNone(self.target.error)
        self.dispatch.assert_called_once()

    def test_a_retry_keeps_what_already_reached_the_platform(self):
        PublicationTarget.objects.filter(pk=self.target.pk).update(
            status=Status.FAILED,
            uploaded_media_id="vid_abc123",
            resume_state={"session_uri": "https://upload/x", "offset": 4096},
        )

        self.client.post(self.url("retry"))

        self.target.refresh_from_db()
        self.assertEqual(self.target.uploaded_media_id, "vid_abc123")
        self.assertEqual(self.target.resume_state["offset"], 4096)

    def test_retrying_a_running_target_is_refused(self):
        PublicationTarget.objects.filter(pk=self.target.pk).update(status=Status.UPLOADING)

        response = self.client.post(self.url("retry"))

        self.assertEqual(response.status_code, 409)

    def test_another_persons_target_is_not_found(self):
        other = User.objects.create_user("other@example.com", "another-password-99")
        self.client.force_login(other)

        self.assertEqual(self.client.post(self.url("cancel")).status_code, 404)
        self.assertEqual(self.client.post(self.url("retry")).status_code, 404)


class PlatformScenarios(PublishingTestCase):
    def test_the_capabilities_are_served_to_the_browser(self):
        body = self.body(self.client.get("/api/platforms"))

        youtube = body["platforms"]["youtube"]
        self.assertEqual(youtube["label"], "YouTube")
        self.assertEqual(youtube["scheduling"], "native")
        self.assertIn("video/mp4", youtube["supportedMimeTypes"])

    def test_signing_in_is_required(self):
        self.client.logout()

        self.assertEqual(self.client.get("/api/platforms").status_code, 401)


class ContractScenarios(PublishingTestCase):
    def test_the_default_settings_match_the_browsers(self):
        """The composer ships its own defaults so it can render before asking the
        server. If the two drift, a person sees one thing and gets another."""
        from pathlib import Path
        import re

        from platforms.youtube import settings_of

        source = Path(__file__).resolve().parents[3] / "frontend/src/platforms/youtube/settings.ts"
        block = re.search(
            r"YOUTUBE_DEFAULT_SETTINGS: YouTubeSettings = \{(.+?)\};", source.read_text(), re.S
        ).group(1)

        frontend = dict(
            re.findall(r"(\w+):\s*'?([\w]+)'?,", block)
        )
        backend = {key: str(value) for key, value in settings_of({}).as_json().items()}

        for key, value in frontend.items():
            self.assertEqual(
                backend[key].lower(), value.lower(), f"default for {key} differs"
            )
