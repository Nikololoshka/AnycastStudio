from media import storage
from media.models import MediaAsset

from .base import ASSETS_URL, CONTENT, UploadTestCase


class AssetScenarios(UploadTestCase):
    def test_assets_are_listed_with_what_is_used_and_allowed(self):
        self.given_an_asset()

        body = self.body(self.client.get(ASSETS_URL))

        self.assertEqual(len(body["assets"]), 1)
        self.assertEqual(body["usedBytes"], len(CONTENT))
        self.assertEqual(body["quotaBytes"], self.user.max_storage_bytes)

    def test_another_persons_assets_are_not_listed(self):
        self.given_an_asset()
        self.sign_in_as_someone_else()

        self.assertEqual(self.body(self.client.get(ASSETS_URL))["assets"], [])

    def test_deleting_an_asset_removes_its_bytes(self):
        asset = self.given_an_asset()
        path = asset.storage_path

        response = self.client.delete(f"{ASSETS_URL}/{asset.pk}")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(storage.absolute(path).exists())

    def test_another_persons_asset_is_not_found(self):
        asset = self.given_an_asset()
        self.sign_in_as_someone_else()

        response = self.client.delete(f"{ASSETS_URL}/{asset.pk}")

        self.assertEqual(response.status_code, 404)
        self.assertTrue(storage.absolute(asset.storage_path).exists())

    def test_a_deleted_asset_stops_counting_against_the_quota(self):
        asset = self.given_an_asset()

        self.client.delete(f"{ASSETS_URL}/{asset.pk}")

        self.assertEqual(self.body(self.client.get(ASSETS_URL))["usedBytes"], 0)

    def test_an_asset_a_publication_still_needs_cannot_be_deleted(self):
        # Given: an asset with a publication that has not finished
        asset = self.given_an_asset()
        self.given_a_publication_of(asset)

        # When: the person tries to delete it
        response = self.client.delete(f"{ASSETS_URL}/{asset.pk}")

        # Then: it is refused and the file stays
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.body(response)["message"], "asset_in_use")
        self.assertTrue(storage.absolute(asset.storage_path).exists())
        self.assertEqual(MediaAsset.objects.get().status, MediaAsset.Status.READY)
