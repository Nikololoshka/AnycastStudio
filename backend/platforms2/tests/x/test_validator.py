from pathlib import Path
from unittest import TestCase

from platforms2.core import PublishDraft, PublishMedia
from platforms2.x.publish.x_options import XOptions
from platforms2.x.x_capabilities import XCapabilities
from platforms2.x.x_validator import XValidator

MEDIA = PublishMedia(Path("clip.mp4"), 1000, "video/mp4", 10)


def errors_of(draft: PublishDraft, media: PublishMedia = MEDIA) -> tuple[str, ...]:
    return XValidator(XCapabilities()).validate(draft, media).errors


class XValidatorScenarios(TestCase):
    def test_a_short_clip_is_valid(self):
        self.assertEqual(errors_of(PublishDraft("Title", "")), ())

    def test_text_is_counted_in_utf16_units_as_the_browser_counts_it(self):
        self.assertEqual(errors_of(PublishDraft("😀" * 140, "")), ())
        self.assertEqual(errors_of(PublishDraft("😀" * 141, "")), ("captionTooLong",))

    def test_the_desktop_limits_hold(self):
        self.assertEqual(errors_of(PublishDraft("T", ""), PublishMedia(Path("c.mp4"), 1, "video/mp4", 0.4)), ("videoTooShort",))
        self.assertEqual(errors_of(PublishDraft("T", ""), PublishMedia(Path("c.mp4"), 1, "video/mp4", 141)), ("videoTooLong",))
        self.assertEqual(
            errors_of(PublishDraft("T", ""), PublishMedia(Path("c.webm"), 513 * 1024**2, "video/webm")),
            ("fileTooLarge", "unsupportedType"),
        )


class XOptionsScenarios(TestCase):
    def test_the_defaults_add_no_fields_to_the_post(self):
        self.assertEqual(XOptions.of({}).as_post_fields(), {})

    def test_only_a_true_flag_is_sent(self):
        options = XOptions.of({"madeWithAi": "yes", "paidPartnership": True, "superFollowersOnly": True, "replyAudience": "nobody"})

        self.assertEqual(options.as_post_fields(), {"paid_partnership": True, "for_super_followers_only": True})
