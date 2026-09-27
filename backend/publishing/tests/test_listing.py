from unittest import mock

from accounts.models import User
from publishing.models import PublicationTarget

from .base import LIST_URL, PublishingTestCase

Status = PublicationTarget.Status


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
