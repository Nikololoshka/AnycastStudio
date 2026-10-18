from unittest import mock

from accounts.models import User
from publishing.models import Publication, PublicationTarget

from .base import LIST_URL, PublishingTestCase

Status = PublicationTarget.Status


class DeleteScenarios(PublishingTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("services.tasks.run_target.delay")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.publication = self.body(self.create_publication())["publication"]

    def delete(self):
        return self.client.delete(f"{LIST_URL}/{self.publication['id']}/delete")

    def given_finished(self, status=Status.COMPLETED):
        PublicationTarget.objects.update(status=status)

    def test_a_finished_publication_disappears_from_the_list_and_its_page(self):
        self.given_finished()

        response = self.delete()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.body(self.client.get(LIST_URL))["publications"], [])
        self.assertEqual(self.client.get(f"{LIST_URL}/{self.publication['id']}").status_code, 404)

    def test_the_row_is_kept_so_the_file_and_the_daily_limit_still_count_it(self):
        self.given_finished()

        self.delete()

        self.assertIsNotNone(Publication.objects.get().hidden_at)

    def test_a_publication_still_running_is_refused(self):
        # Given: a target still uploading
        PublicationTarget.objects.update(status=Status.UPLOADING)

        # When: the person deletes it
        response = self.delete()

        # Then: it stays, so the person still sees what is in progress
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.body(response)["message"], "publication_active")
        self.assertIsNone(Publication.objects.get().hidden_at)

    def test_a_failed_publication_can_be_deleted(self):
        self.given_finished(Status.FAILED)

        self.assertEqual(self.delete().status_code, 200)

    def test_another_persons_publication_is_not_found(self):
        self.given_finished()
        other = User.objects.create_user("other@example.com", "another-password-99")
        self.client.force_login(other)

        self.assertEqual(self.delete().status_code, 404)
        self.assertIsNone(Publication.objects.get().hidden_at)

    def test_deleting_twice_is_not_found(self):
        self.given_finished()
        self.delete()

        self.assertEqual(self.delete().status_code, 404)

    def test_a_target_of_a_deleted_publication_cannot_be_retried(self):
        # Given: a failed publication the person deleted
        self.given_finished(Status.FAILED)
        self.delete()

        # When: someone retries its target by id
        response = self.client.post(f"/api/targets/{self.only_target().pk}/retry")

        # Then: it is not found, so it does not come back to life unseen
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.only_target().status, Status.FAILED)
