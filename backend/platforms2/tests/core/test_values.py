
from platforms2 import PlatformCatalog, PlatformConfigs
from platforms2.core import (
    Pkce,
    PlatformError,
    PlatformFailure,
    PlatformType,
    PublishDraft,
    Scheduling,
    UploadProgress,
    VideoFile,
)
from platforms2.instagram import InstagramConfig
from platforms2.tiktok import TikTokConfig
from platforms2.x import XConfig
from platforms2.youtube import YouTubeConfig

from ..base import CONTENT, PlatformTestCase


class PkceScenarios(PlatformTestCase):
    def test_the_standard_challenge_matches_rfc_7636(self):
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        self.assertEqual(Pkce(verifier).challenge(), "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")

    def test_the_hex_challenge_is_the_same_digest_in_lowercase_hex(self):
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        self.assertEqual(
            Pkce(verifier).hex_challenge(), "13d31e961a1ad8ec2f16b10c4c982e0876a878ad6df144566ee1894acb70f9c3"
        )

    def test_every_verifier_is_new(self):
        self.assertNotEqual(Pkce.generate().verifier, Pkce.generate().verifier)


class DraftScenarios(PlatformTestCase):
    def test_the_caption_joins_title_description_and_hashtags(self):
        self.assertEqual(PublishDraft("Title", "Body", ("a", "b")).caption(), "Title\n\nBody\n\n#a #b")

    def test_an_empty_part_leaves_no_blank_lines(self):
        self.assertEqual(PublishDraft("Title", "", ("a",)).caption(), "Title\n\n#a")

    def test_surrounding_whitespace_is_trimmed(self):
        self.assertEqual(PublishDraft("  Title ", "\nBody\n").caption(), "Title\n\nBody")


class UploadProgressScenarios(PlatformTestCase):
    def test_the_percent_is_whole(self):
        self.assertEqual(UploadProgress(1, 3).percent, 33)

    def test_an_empty_file_is_complete(self):
        self.assertEqual(UploadProgress(0, 0).percent, 100)

    def test_only_an_event_with_a_media_id_ends_the_upload(self):
        self.assertFalse(UploadProgress(10, 10).done)
        self.assertTrue(UploadProgress(10, 10, media_id="m").done)


class VideoFileScenarios(PlatformTestCase):
    async def test_a_piece_is_read_at_its_offset(self):
        self.assertEqual(await VideoFile(self.given_file()).piece(10, 5), CONTENT[10:15])

    async def test_a_missing_file_is_media_missing(self):
        path = self.given_file()
        path.unlink()

        with self.assertRaises(PlatformError) as raised:
            await VideoFile(path).piece(0, 5)

        self.assertEqual(raised.exception.failure, PlatformFailure.MEDIA_MISSING)

    async def test_a_file_shorter_than_declared_is_media_missing(self):
        with self.assertRaises(PlatformError) as raised:
            await VideoFile(self.given_file(b"short")).piece(0, 100)

        self.assertEqual(raised.exception.failure, PlatformFailure.MEDIA_MISSING)


class CatalogScenarios(PlatformTestCase):
    def catalog(self, **overrides) -> PlatformCatalog:
        configs = {
            "youtube": YouTubeConfig("id", "secret", "uri"),
            "tiktok": TikTokConfig("key", "secret", "uri"),
            "instagram": InstagramConfig("id", "secret", "uri"),
            "x": XConfig("id", "secret", "uri"),
            **overrides,
        }
        return PlatformCatalog(PlatformConfigs(**configs), self.http)

    def test_every_platform_is_found_by_its_type(self):
        catalog = self.catalog()

        for platform_type in PlatformType:
            with self.subTest(platform=platform_type):
                self.assertEqual(catalog.get(platform_type).platform_type, platform_type)

    def test_the_platforms_that_upload_at_the_scheduled_time_are_named(self):
        self.assertEqual(
            self.catalog().deferring_upload(), (PlatformType.TIKTOK, PlatformType.INSTAGRAM, PlatformType.X)
        )

    def test_a_platform_without_credentials_is_not_configured(self):
        catalog = self.catalog(x=XConfig("id", "", "uri"))

        self.assertFalse(catalog.get(PlatformType.X).configured)
        self.assertTrue(catalog.get(PlatformType.YOUTUBE).configured)

    def test_capabilities_keep_the_json_the_composer_reads(self):
        capabilities = self.catalog().get(PlatformType.TIKTOK).capabilities.as_json()

        self.assertEqual(capabilities["scheduling"], Scheduling.DEFERRED_UPLOAD.value)
        self.assertEqual(capabilities["maxFileSize"], 4 * 1024**3)
        self.assertIn("video/mp4", capabilities["supportedMimeTypes"])
