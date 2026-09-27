from media import services, storage
from media.models import MediaAsset, UploadSession

from .base import CHUNK_SIZE, CONTENT, UploadTestCase, sha256_of


class CompleteScenarios(UploadTestCase):
    def test_a_finished_transfer_becomes_an_asset(self):
        upload_id = self.started_upload_id()
        self.send_all(upload_id)

        response = self.complete(upload_id, durationSeconds=12.5, width=1920, height=1080)

        body = self.body(response)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["asset"]["sizeBytes"], len(CONTENT))
        self.assertEqual(body["asset"]["width"], 1920)
        asset = MediaAsset.objects.get()
        self.assertEqual(asset.duration_seconds, 12.5)
        self.assertEqual(asset.status, MediaAsset.Status.READY)

    def test_the_bytes_land_where_the_asset_says_they_are(self):
        asset = self.given_an_asset()

        self.assertEqual(storage.absolute(asset.storage_path).read_bytes(), CONTENT)

    def test_a_file_that_does_not_match_its_checksum_is_rejected(self):
        # Given: a transfer whose declared hash belongs to different bytes
        upload_id = self.started_upload_id(checksum=sha256_of(b"something else"))
        self.send_all(upload_id)

        response = self.complete(upload_id)

        # Then: no asset is created, and the partial file is gone
        session = UploadSession.objects.get()
        self.assertEqual(response.status_code, 400)
        self.assertFalse(MediaAsset.objects.exists())
        self.assertEqual(session.status, UploadSession.Status.ABORTED)
        self.assertFalse(storage.absolute(session.storage_path).exists())

    def test_completing_early_reports_how_far_the_server_got(self):
        upload_id = self.started_upload_id()
        self.send_chunk(upload_id, CONTENT[:CHUNK_SIZE], 0)

        response = self.complete(upload_id)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.body(response)["offset"], CHUNK_SIZE)
        self.assertEqual(self.body(response)["expected"], len(CONTENT))

    def test_completing_twice_is_refused(self):
        upload_id = self.started_upload_id()
        self.send_all(upload_id)
        self.complete(upload_id)

        response = self.complete(upload_id)

        self.assertEqual(response.status_code, 410)
        self.assertEqual(MediaAsset.objects.count(), 1)

    def test_two_completions_racing_make_one_asset(self):
        # Given: two requests that both saw the transfer still open
        upload_id = self.started_upload_id()
        self.send_all(upload_id)
        first_copy = UploadSession.objects.get(upload_id=upload_id)
        second_copy = UploadSession.objects.get(upload_id=upload_id)
        services.complete(first_copy)

        # When / Then: the second is refused instead of failing on the moved file
        with self.assertRaises(services.AlreadyFinished):
            services.complete(second_copy)
        self.assertEqual(MediaAsset.objects.count(), 1)
