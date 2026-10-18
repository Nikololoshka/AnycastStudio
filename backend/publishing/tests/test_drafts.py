from accounts.models import User
from media.models import MediaAsset
from publishing.models import Draft

from .base import PublishingTestCase

DRAFTS_URL = "/api/drafts"


class DraftScenarios(PublishingTestCase):
    def save_draft(self, url=f"{DRAFTS_URL}/create", **overrides):
        payload = {
            "mediaAssetId": self.asset.pk,
            "title": "Work in progress",
            "hashtags": ["one"],
            "selectedPlatforms": ["youtube", "x"],
            "platformSettings": {"youtube": {"privacyStatus": "unlisted"}},
            **overrides,
        }
        return self.client.post(url, data=payload, content_type="application/json")

    def saved_draft(self, **overrides) -> dict:
        return self.body(self.save_draft(**overrides))["draft"]

    def sign_in_as_someone_else(self) -> User:
        other = User.objects.create_user("other@example.com", "another-password-99")
        self.client.force_login(other)
        return other

    def test_a_saved_draft_comes_back_with_its_video(self):
        draft = self.saved_draft()

        body = self.body(self.client.get(f"{DRAFTS_URL}/{draft['id']}"))["draft"]

        self.assertEqual(body["title"], "Work in progress")
        self.assertEqual(body["video"]["id"], self.asset.pk)
        self.assertEqual(body["selectedPlatforms"], ["youtube", "x"])
        self.assertEqual(body["platformSettings"], {"youtube": {"privacyStatus": "unlisted"}})

    def test_drafts_are_listed_most_recently_changed_first(self):
        first = self.saved_draft(title="First")
        self.saved_draft(title="Second")
        self.save_draft(url=f"{DRAFTS_URL}/{first['id']}/update", title="First again")

        rows = self.body(self.client.get(DRAFTS_URL))["drafts"]

        self.assertEqual([row["title"] for row in rows], ["First again", "Second"])

    def test_an_update_replaces_the_whole_draft(self):
        draft = self.saved_draft()

        response = self.client.post(
            f"{DRAFTS_URL}/{draft['id']}/update", data={"title": "Only a title"}, content_type="application/json"
        )

        body = self.body(response)["draft"]
        self.assertIsNone(body["video"])
        self.assertEqual(body["hashtags"], [])
        self.assertEqual(body["platformSettings"], {})

    def test_a_deleted_draft_is_gone(self):
        draft = self.saved_draft()

        response = self.client.delete(f"{DRAFTS_URL}/{draft['id']}/delete")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Draft.objects.exists())

    def test_a_draft_without_a_video_can_be_saved(self):
        draft = self.saved_draft(mediaAssetId=None)

        self.assertIsNone(draft["video"])

    def test_a_draft_whose_file_was_deleted_has_no_video(self):
        draft = self.saved_draft()
        MediaAsset.objects.update(status=MediaAsset.Status.DELETED)

        body = self.body(self.client.get(f"{DRAFTS_URL}/{draft['id']}"))["draft"]

        self.assertIsNone(body["video"])

    def test_another_persons_draft_is_not_found(self):
        # Given: a draft of someone else
        draft = self.saved_draft()
        self.sign_in_as_someone_else()

        # When / Then: reading, replacing and deleting all answer 404
        self.assertEqual(self.client.get(f"{DRAFTS_URL}/{draft['id']}").status_code, 404)
        self.assertEqual(
            self.save_draft(url=f"{DRAFTS_URL}/{draft['id']}/update", mediaAssetId=None).status_code, 404
        )
        self.assertEqual(self.client.delete(f"{DRAFTS_URL}/{draft['id']}/delete").status_code, 404)
        self.assertEqual(self.body(self.client.get(DRAFTS_URL))["drafts"], [])
        self.assertEqual(Draft.objects.get().title, "Work in progress")

    def test_another_persons_video_cannot_be_put_in_a_draft(self):
        self.sign_in_as_someone_else()

        response = self.save_draft()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.body(response)["errors"][0]["field"], "mediaAssetId")

    def test_an_unknown_platform_is_refused(self):
        response = self.save_draft(platformSettings={"myspace": {}})

        self.assertEqual(response.status_code, 400)

    def test_a_setting_the_platform_does_not_have_is_refused(self):
        response = self.save_draft(platformSettings={"x": {"replyAudience": "everyone", "pinned": True}})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Draft.objects.exists())

    def test_a_platform_selected_twice_is_refused(self):
        response = self.save_draft(selectedPlatforms=["x", "x"])

        self.assertEqual(response.status_code, 400)

    def test_signing_in_is_required(self):
        self.client.logout()

        self.assertEqual(self.client.get(DRAFTS_URL).status_code, 401)
