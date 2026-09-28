from platforms.core.errors import FailureType
from platforms.tiktok import caption_of, failure_of, fetch_status, validate, video_options_of
from platforms.tiktok.status import FAIL_REASONS
from platforms.upload import NeedsFreshToken

from .base import FakeResponse, PlatformTestCase


def status(data: dict) -> FakeResponse:
    return FakeResponse(200, {"data": data, "error": {"code": "ok"}})


class PublishStatusScenarios(PlatformTestCase):
    def test_a_finished_post_reports_its_public_id(self):
        # TikTok spells the field "publicaly"
        self.http.side_effect = [status({"status": "PUBLISH_COMPLETE", "publicaly_available_post_id": [7123]})]

        result = fetch_status("act.token", "v_pub_1")

        self.assertTrue(result.is_complete)
        self.assertEqual(result.post_ids, ("7123",))

    def test_a_post_still_processing_is_neither_complete_nor_failed(self):
        self.http.side_effect = [status({"status": "PROCESSING_UPLOAD"})]

        result = fetch_status("act.token", "v_pub_1")

        self.assertFalse(result.is_complete)
        self.assertFalse(result.is_failed)

    def test_a_failed_post_reports_why(self):
        self.http.side_effect = [status({"status": "FAILED", "fail_reason": "duration_check_failed"})]

        result = fetch_status("act.token", "v_pub_1")

        self.assertTrue(result.is_failed)
        self.assertEqual(result.fail_reason, "duration_check_failed")

    def test_a_rejected_token_asks_for_a_fresh_one(self):
        self.http.side_effect = [FakeResponse(401, {"error": {"code": "access_token_invalid"}})]

        with self.assertRaises(NeedsFreshToken):
            fetch_status("act.token", "v_pub_1")

    def test_every_known_fail_reason_has_its_own_message(self):
        for reason in FAIL_REASONS:
            failure = failure_of(reason)
            self.assertEqual(failure.details, reason)
            self.assertNotEqual(failure.message, failure_of("something_new").message)

    def test_a_revoked_authorisation_is_an_authentication_failure(self):
        self.assertEqual(failure_of("auth_removed").type, FailureType.AUTHENTICATION)

    def test_a_rejected_format_is_a_file_failure(self):
        self.assertEqual(failure_of("file_format_check_failed").type, FailureType.FILE)

    def test_an_unknown_reason_is_a_platform_failure(self):
        self.assertEqual(failure_of("something_new").type, FailureType.PLATFORM)


class ValidationScenarios(PlatformTestCase):
    def check(self, caption="A video", size=1024, mime="video/mp4", **settings):
        options = video_options_of({"privacyLevel": "SELF_ONLY", **settings})
        return validate(caption=caption, options=options, size_bytes=size, mime_type=mime)

    def test_a_complete_post_is_valid(self):
        self.assertTrue(self.check().valid)

    def test_the_privacy_level_must_be_chosen(self):
        self.assertIn("privacyRequired", self.check(privacyLevel=None).errors)

    def test_an_unknown_privacy_level_counts_as_not_chosen(self):
        self.assertIn("privacyRequired", self.check(privacyLevel="EVERYONE").errors)

    def test_the_caption_limit_counts_utf16_units(self):
        # An emoji is two UTF-16 units, so 1101 of them exceed 2200
        self.assertIn("captionTooLong", self.check(caption="😀" * 1101).errors)
        self.assertTrue(self.check(caption="😀" * 1100).valid)

    def test_disclosed_content_must_say_whose_it_is(self):
        self.assertIn("commercialContentUnspecified", self.check(discloseContent=True).errors)

    def test_branded_content_cannot_be_private(self):
        errors = self.check(discloseContent=True, brandContent=True).errors
        self.assertIn("brandedContentCannotBePrivate", errors)

    def test_brand_toggles_are_sent_only_when_disclosed(self):
        options = video_options_of({"brandContent": True, "brandOrganic": True})
        self.assertFalse(options.brand_content_toggle)
        self.assertFalse(options.brand_organic_toggle)

    def test_an_unsupported_type_is_refused(self):
        self.assertIn("unsupportedType", self.check(mime="video/x-flv").errors)

    def test_the_caption_joins_title_description_and_hashtags(self):
        self.assertEqual(caption_of("Title", "About", ["one", "two"]), "Title\n\nAbout\n\n#one #two")

    def test_an_empty_part_leaves_no_blank_lines(self):
        self.assertEqual(caption_of("Title", "", []), "Title")

    def test_a_cover_frame_becomes_milliseconds(self):
        self.assertEqual(video_options_of({"coverFrameSeconds": 1.5}).cover_timestamp_ms, 1500)
        self.assertIsNone(video_options_of({"coverFrameSeconds": 0}).cover_timestamp_ms)
        self.assertIsNone(video_options_of({"coverFrameSeconds": "3"}).cover_timestamp_ms)
