from pathlib import Path
from unittest import TestCase

from platforms2.core import PublishDraft, PublishMedia
from platforms2.youtube.youtube_capabilities import YouTubeCapabilities
from platforms2.youtube.youtube_validator import YouTubeValidator

MEDIA = PublishMedia(Path("clip.mp4"), 1000, "video/mp4", 10)


def errors_of(draft: PublishDraft, media: PublishMedia = MEDIA) -> tuple[str, ...]:
    return YouTubeValidator(YouTubeCapabilities()).validate(draft, media).errors


class YouTubeValidatorScenarios(TestCase):
    def test_a_titled_video_is_valid(self):
        self.assertEqual(errors_of(PublishDraft("Title", "Body")), ())

    def test_the_title_is_required(self):
        self.assertEqual(errors_of(PublishDraft("   ", "")), ("titleRequired",))

    def test_each_limit_has_its_own_error(self):
        # Given: a draft over every limit and a file YouTube does not take
        draft = PublishDraft("t" * 101, "d" * 5001)
        media = PublishMedia(Path("clip.mkv"), 129 * 1024**3, "video/x-matroska")

        # When / Then: each limit is named
        self.assertEqual(
            errors_of(draft, media), ("titleTooLong", "descriptionTooLong", "fileTooLarge", "unsupportedType")
        )

    def test_an_unknown_type_is_left_to_youtube(self):
        self.assertEqual(errors_of(PublishDraft("Title", ""), PublishMedia(Path("clip"), 1000, "")), ())
