from pathlib import Path
from unittest import TestCase

from platforms2.core import PublishDraft, PublishMedia
from platforms2.tiktok.publish.tiktok_options import TikTokOptions
from platforms2.tiktok.tiktok_capabilities import TikTokCapabilities
from platforms2.tiktok.tiktok_validator import TikTokValidator

MEDIA = PublishMedia(Path("clip.mp4"), 1000, "video/mp4", 10)
PRIVATE = {"privacyLevel": "SELF_ONLY"}


def errors_of(settings: dict, title: str = "Title", media: PublishMedia = MEDIA) -> tuple[str, ...]:
    return TikTokValidator(TikTokCapabilities()).validate(PublishDraft(title, "", (), settings), media).errors


class TikTokValidatorScenarios(TestCase):
    def test_a_complete_post_is_valid(self):
        self.assertEqual(errors_of(PRIVATE), ())

    def test_the_privacy_level_must_be_chosen(self):
        self.assertEqual(errors_of({}), ("privacyRequired",))

    def test_an_unknown_privacy_level_counts_as_not_chosen(self):
        self.assertEqual(errors_of({"privacyLevel": "EVERYONE"}), ("privacyRequired",))

    def test_the_caption_limit_counts_utf16_units(self):
        self.assertEqual(errors_of(PRIVATE, title="😀" * 1100), ())
        self.assertEqual(errors_of(PRIVATE, title="😀" * 1101), ("captionTooLong",))

    def test_disclosed_content_must_say_whose_it_is(self):
        self.assertEqual(errors_of({**PRIVATE, "discloseContent": True}), ("commercialContentUnspecified",))

    def test_branded_content_cannot_be_private(self):
        settings = {**PRIVATE, "discloseContent": True, "brandContent": True}

        self.assertEqual(errors_of(settings), ("brandedContentCannotBePrivate",))

    def test_an_unsupported_type_is_refused(self):
        media = PublishMedia(Path("clip.avi"), 1000, "video/x-msvideo")

        self.assertEqual(errors_of(PRIVATE, media=media), ("unsupportedType",))


class TikTokOptionsScenarios(TestCase):
    def test_brand_toggles_are_sent_only_when_disclosed(self):
        hidden = TikTokOptions.of({"brandContent": True, "brandOrganic": True})
        disclosed = TikTokOptions.of({"discloseContent": True, "brandContent": True, "brandOrganic": True})

        self.assertEqual((hidden.brand_content_toggle, hidden.brand_organic_toggle), (False, False))
        self.assertEqual((disclosed.brand_content_toggle, disclosed.brand_organic_toggle), (True, True))

    def test_a_cover_frame_becomes_milliseconds(self):
        self.assertEqual(TikTokOptions.of({"coverFrameSeconds": 1.5}).cover_timestamp_ms, 1500)
        self.assertIsNone(TikTokOptions.of({"coverFrameSeconds": True}).cover_timestamp_ms)
