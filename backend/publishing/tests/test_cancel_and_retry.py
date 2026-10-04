from unittest import mock

from accounts.models import User
from publishing.models import PublicationTarget

from .base import PublishingTestCase

Status = PublicationTarget.Status


class CancelAndRetryScenarios(PublishingTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("services.tasks.run_target.delay")
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
            status=Status.FAILED, error={"failure": "network", "message": "lost", "details": ""}
        )
        self.dispatch.reset_mock()

        response = self.client.post(self.url("retry"))

        self.assertEqual(response.status_code, 200)
        self.target.refresh_from_db()
        self.assertEqual(self.target.status, Status.QUEUED)
        self.assertIsNone(self.target.error)
        self.dispatch.assert_called_once()

    def test_a_retry_starts_the_publish_from_scratch(self):
        PublicationTarget.objects.filter(pk=self.target.pk).update(
            status=Status.FAILED,
            uploaded_media_id="vid_abc123",
            confirmation_state={"commit_started": "2026-01-01T12:00:00+00:00", "polls": 3},
        )

        self.client.post(self.url("retry"))

        self.target.refresh_from_db()
        self.assertEqual(self.target.uploaded_media_id, "")
        self.assertIsNone(self.target.confirmation_state)

    def test_retrying_a_running_target_is_refused(self):
        PublicationTarget.objects.filter(pk=self.target.pk).update(status=Status.UPLOADING)

        response = self.client.post(self.url("retry"))

        self.assertEqual(response.status_code, 409)

    def test_another_persons_target_is_not_found(self):
        other = User.objects.create_user("other@example.com", "another-password-99")
        self.client.force_login(other)

        self.assertEqual(self.client.post(self.url("cancel")).status_code, 404)
        self.assertEqual(self.client.post(self.url("retry")).status_code, 404)
