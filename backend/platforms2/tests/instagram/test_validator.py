from pathlib import Path
from unittest import TestCase

from platforms2.core import PublishDraft, PublishMedia
from platforms2.instagram.instagram_capabilities import InstagramCapabilities
from platforms2.instagram.instagram_validator import InstagramValidator
from platforms2.instagram.publish.instagram_options import InstagramOptions

MEDIA = PublishMedia(Path("clip.mp4"), 1000, "video/mp4", 10)


def errors_of(draft: PublishDraft, media: PublishMedia = MEDIA) -> tuple[str, ...]:
    return InstagramValidator(InstagramCapabilities()).validate(draft, media).errors


class InstagramValidatorScenarios(TestCase):
    def test_a_plain_reel_is_valid(self):
        self.assertEqual(errors_of(PublishDraft("Title", "Body")), ())

    def test_each_limit_has_its_own_error(self):
        draft = PublishDraft("t" * 2201, "", tuple(f"tag{n}" for n in range(31)))
        media = PublishMedia(Path("clip.webm"), 301 * 1000**2, "video/webm", 2)

        self.assertEqual(
            errors_of(draft, media),
            ("captionTooLong", "tooManyHashtags", "fileTooLarge", "unsupportedType", "videoTooShort"),
        )

    def test_a_reel_longer_than_fifteen_minutes_is_refused(self):
        self.assertEqual(errors_of(PublishDraft("T", ""), PublishMedia(Path("c.mp4"), 1, "video/mp4", 901)), ("videoTooLong",))

    def test_thirty_hashtags_are_allowed(self):
        self.assertEqual(errors_of(PublishDraft("T", "", tuple(f"tag{n}" for n in range(30)))), ())

    def test_an_unknown_duration_is_left_to_instagram(self):
        self.assertEqual(errors_of(PublishDraft("T", ""), PublishMedia(Path("c.mp4"), 1, "video/mp4", None)), ())


class InstagramOptionsScenarios(TestCase):
    def test_missing_options_fall_back_to_the_defaults(self):
        self.assertEqual(InstagramOptions.of({}), InstagramOptions(share_to_feed=True, cover_frame_seconds=0))

    def test_nonsense_falls_back_rather_than_failing(self):
        self.assertEqual(
            InstagramOptions.of({"shareToFeed": "no", "coverFrameSeconds": "soon"}), InstagramOptions(True, 0)
        )

    def test_the_cover_frame_is_sent_in_milliseconds(self):
        self.assertEqual(InstagramOptions.of({"coverFrameSeconds": 1.25}).thumb_offset_ms, 1250)
