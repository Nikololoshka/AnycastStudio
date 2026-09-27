from django.test import override_settings

from media.models import UploadSession

from .base import CHUNK_SIZE, CONTENT, UploadTestCase


class StartScenarios(UploadTestCase):
    def test_starting_returns_where_to_begin_and_how_big_a_chunk_should_be(self):
        response = self.start()

        body = self.body(response)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["offset"], 0)
        self.assertEqual(body["chunkSize"], CHUNK_SIZE)
        self.assertTrue(body["uploadId"])

    def test_the_chunk_size_is_the_servers_decision(self):
        # Given: the server's chunk size changes, with no new frontend released
        # When / Then: a new upload is told the new size
        with override_settings(UPLOAD_CHUNK_BYTES=4096):
            self.assertEqual(self.body(self.start())["chunkSize"], 4096)

    def test_a_file_over_the_per_file_limit_is_refused_before_any_bytes_move(self):
        self.user.max_media_asset_bytes = len(CONTENT) - 1
        self.user.save()

        response = self.start()

        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.body(response)["status"], "payload_too_large")
        self.assertFalse(UploadSession.objects.exists())

    def test_a_file_that_would_break_the_storage_quota_is_refused(self):
        self.user.max_storage_bytes = len(CONTENT) - 1
        self.user.save()

        response = self.start()

        self.assertEqual(self.body(response)["status"], "quota_exceeded")

    def test_too_many_transfers_at_once_are_refused(self):
        self.user.max_concurrent_uploads = 1
        self.user.save()

        self.start()
        response = self.start()

        self.assertEqual(self.body(response)["status"], "conflict")

    def test_signing_in_is_required(self):
        self.client.logout()

        self.assertEqual(self.start().status_code, 401)
