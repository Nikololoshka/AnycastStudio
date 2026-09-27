from media import storage
from media.models import UploadSession

from .base import CHUNK_SIZE, CONTENT, START_URL, UploadTestCase


class AbortScenarios(UploadTestCase):
    def test_aborting_removes_the_partial_file(self):
        upload_id = self.started_upload_id()
        self.send_chunk(upload_id, CONTENT[:CHUNK_SIZE], 0)
        partial = UploadSession.objects.get().storage_path

        response = self.client.delete(f"{START_URL}/{upload_id}/abort")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(storage.absolute(partial).exists())
        self.assertEqual(UploadSession.objects.get().status, UploadSession.Status.ABORTED)

    def test_aborting_frees_the_quota_it_was_holding(self):
        self.user.max_concurrent_uploads = 1
        self.user.save()
        upload_id = self.started_upload_id()

        self.client.delete(f"{START_URL}/{upload_id}/abort")

        self.assertEqual(self.start().status_code, 200)
