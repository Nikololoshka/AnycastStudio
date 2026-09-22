"""The chunked upload protocol, written as Given / When / Then.

These run against a temporary MEDIA_ROOT: the bytes really are written and read
back, because the parts worth testing are the offsets and the checksum.
"""

import hashlib
import json
import shutil
import tempfile

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from media import storage
from media.models import MediaAsset, UploadSession

START_URL = "/api/media/uploads"
ASSETS_URL = "/api/media/assets"

EMAIL = "person@example.com"
PASSWORD = "correct-horse-battery"

CHUNK_SIZE = 1024
CONTENT = bytes(range(256)) * 20  # 5120 bytes, six chunks of 1 KiB


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class UploadTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_root = tempfile.mkdtemp(prefix="anycast-test-media-")
        cls.override = override_settings(MEDIA_ROOT=cls.media_root, UPLOAD_CHUNK_BYTES=CHUNK_SIZE)
        cls.override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.override.disable()
        shutil.rmtree(cls.media_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(EMAIL, PASSWORD)
        self.client.force_login(self.user)

    def body(self, response) -> dict:
        return json.loads(response.content)

    def start(self, size=len(CONTENT), checksum=None, filename="clip.mp4"):
        return self.client.post(
            START_URL,
            data=json.dumps(
                {
                    "filename": filename,
                    "sizeBytes": size,
                    "mimeType": "video/mp4",
                    "sha256": sha256_of(CONTENT) if checksum is None else checksum,
                }
            ),
            content_type="application/json",
        )

    def send_chunk(self, upload_id, data: bytes, offset: int):
        return self.client.patch(
            f"{START_URL}/{upload_id}",
            data=data,
            content_type="application/octet-stream",
            headers={"Upload-Offset": str(offset)},
        )

    def send_all(self, upload_id, content=CONTENT):
        offset = 0
        while offset < len(content):
            piece = content[offset : offset + CHUNK_SIZE]
            response = self.send_chunk(upload_id, piece, offset)
            offset = self.body(response)["offset"]
        return offset

    def complete(self, upload_id, **fields):
        return self.client.post(
            f"{START_URL}/{upload_id}/complete",
            data=json.dumps(fields),
            content_type="application/json",
        )


class StartScenarios(UploadTestCase):
    def test_starting_returns_where_to_begin_and_how_big_a_chunk_should_be(self):
        response = self.start()

        body = self.body(response)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["offset"], 0)
        self.assertEqual(body["chunkSize"], CHUNK_SIZE)
        self.assertTrue(body["uploadId"])

    def test_the_chunk_size_is_the_servers_decision(self):
        # It is not sent by the client, so it can be tuned without releasing a
        # new frontend.
        with override_settings(UPLOAD_CHUNK_BYTES=4096):
            self.assertEqual(self.body(self.start())["chunkSize"], 4096)

    def test_a_file_over_the_per_file_limit_is_refused_before_any_bytes_move(self):
        quota = self.user.quota
        quota.max_media_asset_bytes = len(CONTENT) - 1
        quota.save()

        response = self.start()

        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.body(response)["status"], "payload_too_large")
        self.assertFalse(UploadSession.objects.exists())

    def test_a_file_that_would_break_the_storage_quota_is_refused(self):
        quota = self.user.quota
        quota.max_storage_bytes = len(CONTENT) - 1
        quota.save()

        response = self.start()

        self.assertEqual(self.body(response)["status"], "quota_exceeded")

    def test_too_many_transfers_at_once_are_refused(self):
        quota = self.user.quota
        quota.max_concurrent_uploads = 1
        quota.save()

        self.start()
        response = self.start()

        self.assertEqual(self.body(response)["status"], "conflict")

    def test_signing_in_is_required(self):
        self.client.logout()

        self.assertEqual(self.start().status_code, 401)


class ChunkScenarios(UploadTestCase):
    def test_chunks_accumulate_and_the_server_reports_the_offset(self):
        upload_id = self.body(self.start())["uploadId"]

        first = self.send_chunk(upload_id, CONTENT[:CHUNK_SIZE], 0)
        second = self.send_chunk(upload_id, CONTENT[CHUNK_SIZE : CHUNK_SIZE * 2], CHUNK_SIZE)

        self.assertEqual(self.body(first)["offset"], CHUNK_SIZE)
        self.assertEqual(self.body(second)["offset"], CHUNK_SIZE * 2)

    def test_a_chunk_at_the_wrong_offset_is_refused_with_the_right_one(self):
        # Given: a transfer that already received one chunk
        upload_id = self.body(self.start())["uploadId"]
        self.send_chunk(upload_id, CONTENT[:CHUNK_SIZE], 0)

        # When: the client resends from a stale position, as it would after a
        # connection dropped mid-chunk
        response = self.send_chunk(upload_id, CONTENT[:CHUNK_SIZE], 0)

        # Then: it is told where the server actually is, and nothing is appended
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.body(response)["offset"], CHUNK_SIZE)
        self.assertEqual(UploadSession.objects.get().received_bytes, CHUNK_SIZE)

    def test_a_transfer_resumes_from_the_reported_offset(self):
        # Given: a transfer interrupted halfway
        upload_id = self.body(self.start())["uploadId"]
        self.send_chunk(upload_id, CONTENT[:CHUNK_SIZE], 0)

        # When: the client asks where to continue and sends the rest
        offset = self.body(self.client.get(f"{START_URL}/{upload_id}/status"))["offset"]
        while offset < len(CONTENT):
            offset = self.body(
                self.send_chunk(upload_id, CONTENT[offset : offset + CHUNK_SIZE], offset)
            )["offset"]

        # Then: the file is whole and its checksum matches
        self.complete(upload_id)
        asset = MediaAsset.objects.get()
        self.assertEqual(asset.size_bytes, len(CONTENT))
        self.assertEqual(asset.sha256, sha256_of(CONTENT))

    def test_more_bytes_than_declared_abort_the_transfer(self):
        upload_id = self.body(self.start(size=CHUNK_SIZE))["uploadId"]

        response = self.send_chunk(upload_id, CONTENT[: CHUNK_SIZE * 2], 0)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(UploadSession.objects.get().status, UploadSession.Status.ABORTED)

    def test_a_missing_offset_header_is_refused(self):
        upload_id = self.body(self.start())["uploadId"]

        response = self.client.patch(
            f"{START_URL}/{upload_id}",
            data=CONTENT[:CHUNK_SIZE],
            content_type="application/octet-stream",
        )

        self.assertEqual(response.status_code, 400)

    def test_another_persons_transfer_is_not_found(self):
        upload_id = self.body(self.start())["uploadId"]
        other = User.objects.create_user("other@example.com", "another-password-99")
        self.client.force_login(other)

        response = self.send_chunk(upload_id, CONTENT[:CHUNK_SIZE], 0)

        self.assertEqual(response.status_code, 404)

    def test_a_stale_transfer_is_expired_and_its_bytes_dropped(self):
        # Given: a transfer nobody touched for longer than its time to live
        upload_id = self.body(self.start())["uploadId"]
        self.send_chunk(upload_id, CONTENT[:CHUNK_SIZE], 0)
        UploadSession.objects.update(last_activity_at=UploadSession.stale_cutoff())

        response = self.send_chunk(upload_id, CONTENT[:CHUNK_SIZE], CHUNK_SIZE)

        self.assertEqual(response.status_code, 410)

    def test_post_is_not_allowed_on_the_chunk_endpoint(self):
        upload_id = self.body(self.start())["uploadId"]

        response = self.client.put(f"{START_URL}/{upload_id}", data=b"x")

        self.assertEqual(response.status_code, 405)


class CompleteScenarios(UploadTestCase):
    def test_a_finished_transfer_becomes_an_asset(self):
        upload_id = self.body(self.start())["uploadId"]
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
        upload_id = self.body(self.start())["uploadId"]
        self.send_all(upload_id)
        self.complete(upload_id)

        asset = MediaAsset.objects.get()

        self.assertEqual(storage.absolute(asset.storage_path).read_bytes(), CONTENT)

    def test_a_file_that_does_not_match_its_checksum_is_rejected(self):
        # Given: a transfer whose declared hash belongs to different bytes
        upload_id = self.body(self.start(checksum=sha256_of(b"something else")))["uploadId"]
        self.send_all(upload_id)

        response = self.complete(upload_id)

        # Then: no asset is created, and the partial file is gone
        self.assertEqual(response.status_code, 400)
        self.assertFalse(MediaAsset.objects.exists())
        self.assertEqual(UploadSession.objects.get().status, UploadSession.Status.ABORTED)

    def test_completing_early_reports_how_far_the_server_got(self):
        upload_id = self.body(self.start())["uploadId"]
        self.send_chunk(upload_id, CONTENT[:CHUNK_SIZE], 0)

        response = self.complete(upload_id)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.body(response)["offset"], CHUNK_SIZE)
        self.assertEqual(self.body(response)["expected"], len(CONTENT))

    def test_completing_twice_is_refused(self):
        upload_id = self.body(self.start())["uploadId"]
        self.send_all(upload_id)
        self.complete(upload_id)

        response = self.complete(upload_id)

        self.assertEqual(response.status_code, 410)
        self.assertEqual(MediaAsset.objects.count(), 1)


class AbortScenarios(UploadTestCase):
    def test_aborting_removes_the_partial_file(self):
        upload_id = self.body(self.start())["uploadId"]
        self.send_chunk(upload_id, CONTENT[:CHUNK_SIZE], 0)
        partial = UploadSession.objects.get().storage_path

        response = self.client.delete(f"{START_URL}/{upload_id}/abort")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(storage.absolute(partial).exists())
        self.assertEqual(UploadSession.objects.get().status, UploadSession.Status.ABORTED)

    def test_aborting_frees_the_quota_it_was_holding(self):
        quota = self.user.quota
        quota.max_concurrent_uploads = 1
        quota.save()
        upload_id = self.body(self.start())["uploadId"]

        self.client.delete(f"{START_URL}/{upload_id}/abort")

        self.assertEqual(self.start().status_code, 200)


class AssetScenarios(UploadTestCase):
    def given_an_asset(self) -> MediaAsset:
        upload_id = self.body(self.start())["uploadId"]
        self.send_all(upload_id)
        self.complete(upload_id)
        return MediaAsset.objects.get()

    def test_assets_are_listed_with_what_is_used_and_allowed(self):
        self.given_an_asset()

        body = self.body(self.client.get(ASSETS_URL))

        self.assertEqual(len(body["assets"]), 1)
        self.assertEqual(body["usedBytes"], len(CONTENT))
        self.assertEqual(body["quotaBytes"], self.user.quota.max_storage_bytes)

    def test_another_persons_assets_are_not_listed(self):
        self.given_an_asset()
        other = User.objects.create_user("other@example.com", "another-password-99")
        self.client.force_login(other)

        self.assertEqual(self.body(self.client.get(ASSETS_URL))["assets"], [])

    def test_deleting_an_asset_removes_its_bytes(self):
        asset = self.given_an_asset()
        path = asset.storage_path

        response = self.client.delete(f"{ASSETS_URL}/{asset.pk}")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(storage.absolute(path).exists())

    def test_another_persons_asset_is_not_found(self):
        asset = self.given_an_asset()
        other = User.objects.create_user("other@example.com", "another-password-99")
        self.client.force_login(other)

        response = self.client.delete(f"{ASSETS_URL}/{asset.pk}")

        self.assertEqual(response.status_code, 404)
        self.assertTrue(storage.absolute(asset.storage_path).exists())

    def test_a_deleted_asset_stops_counting_against_the_quota(self):
        asset = self.given_an_asset()

        self.client.delete(f"{ASSETS_URL}/{asset.pk}")

        self.assertEqual(self.body(self.client.get(ASSETS_URL))["usedBytes"], 0)


class SweepScenarios(UploadTestCase):
    def test_a_stale_session_is_swept_with_its_partial_file(self):
        from media.tasks import sweep_upload_sessions

        upload_id = self.body(self.start())["uploadId"]
        self.send_chunk(upload_id, CONTENT[:CHUNK_SIZE], 0)
        partial = UploadSession.objects.get().storage_path
        UploadSession.objects.update(last_activity_at=UploadSession.stale_cutoff())

        swept = sweep_upload_sessions()

        self.assertEqual(swept, 1)
        self.assertFalse(storage.absolute(partial).exists())
        self.assertEqual(UploadSession.objects.get().status, UploadSession.Status.ABORTED)

    def test_an_asset_nobody_published_is_swept_once_it_is_old_enough(self):
        from media.tasks import sweep_orphan_assets

        upload_id = self.body(self.start())["uploadId"]
        self.send_all(upload_id)
        self.complete(upload_id)
        asset = MediaAsset.objects.get()
        path = asset.storage_path
        MediaAsset.objects.update(created_at=timezone.now() - timezone.timedelta(days=30))

        swept = sweep_orphan_assets()

        self.assertEqual(swept, 1)
        self.assertFalse(storage.absolute(path).exists())
        self.assertEqual(MediaAsset.objects.get().status, MediaAsset.Status.DELETED)

    def test_a_recent_asset_is_left_alone(self):
        from media.tasks import sweep_orphan_assets

        self.given_recent_asset()

        self.assertEqual(sweep_orphan_assets(), 0)
        self.assertEqual(MediaAsset.objects.get().status, MediaAsset.Status.READY)

    def given_recent_asset(self):
        upload_id = self.body(self.start())["uploadId"]
        self.send_all(upload_id)
        self.complete(upload_id)
