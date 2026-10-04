from datetime import timedelta

from django.utils import timezone

from media import storage
from media.models import MediaAsset, UploadSession
from media.services import sweep_unused_assets, sweep_upload_sessions

from .base import CHUNK_SIZE, CONTENT, UploadTestCase

LONG_AGO = timedelta(days=30)


class SessionSweepScenarios(UploadTestCase):
    def test_a_stale_session_is_swept_with_its_partial_file(self):
        upload_id = self.started_upload_id()
        self.send_chunk(upload_id, CONTENT[:CHUNK_SIZE], 0)
        partial = UploadSession.objects.get().storage_path
        UploadSession.objects.update(last_activity_at=UploadSession.stale_cutoff())

        swept = sweep_upload_sessions()

        self.assertEqual(swept, 1)
        self.assertFalse(storage.absolute(partial).exists())
        self.assertEqual(UploadSession.objects.get().status, UploadSession.Status.ABORTED)


class AssetSweepScenarios(UploadTestCase):
    def given_an_old_asset(self) -> MediaAsset:
        asset = self.given_an_asset()
        MediaAsset.objects.update(created_at=timezone.now() - LONG_AGO)
        return asset

    def assert_kept(self, asset: MediaAsset):
        self.assertEqual(sweep_unused_assets(), 0)
        self.assertTrue(storage.absolute(asset.storage_path).exists())

    def test_an_asset_nobody_published_is_swept_once_it_is_old_enough(self):
        asset = self.given_an_old_asset()

        swept = sweep_unused_assets()

        self.assertEqual(swept, 1)
        self.assertFalse(storage.absolute(asset.storage_path).exists())
        self.assertEqual(MediaAsset.objects.get().status, MediaAsset.Status.DELETED)

    def test_a_recent_asset_is_left_alone(self):
        asset = self.given_an_asset()

        self.assert_kept(asset)

    def test_an_old_asset_a_publication_still_needs_is_kept(self):
        # Given: an old asset whose publication has not finished
        asset = self.given_an_old_asset()
        self.given_a_publication_of(asset)

        # When / Then: the sweep leaves it, so the upload can still read it
        self.assert_kept(asset)

    def test_a_published_asset_is_kept_for_the_retention_period(self):
        # Given: an old asset whose publication finished an hour ago
        asset = self.given_an_old_asset()
        self.given_a_publication_of(asset, finished_at=timezone.now() - timedelta(hours=1))

        # When / Then: it stays, so a failed target can still be retried
        self.assert_kept(asset)

    def test_a_published_asset_goes_once_the_retention_period_is_over(self):
        # Given: an asset whose publication finished long ago
        asset = self.given_an_old_asset()
        self.given_a_publication_of(asset, finished_at=timezone.now() - LONG_AGO)

        # When: the sweep runs
        swept = sweep_unused_assets()

        # Then: nothing needs the file any more, so it is deleted
        self.assertEqual(swept, 1)
        self.assertFalse(storage.absolute(asset.storage_path).exists())
