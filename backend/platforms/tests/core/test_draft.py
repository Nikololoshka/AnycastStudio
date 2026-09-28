from django.test import SimpleTestCase

from platforms.core.publishing import MediaInfo, PublicationDraft


def draft(title: str, description: str, hashtags: tuple[str, ...]) -> PublicationDraft:
    return PublicationDraft(title, description, hashtags, MediaInfo(1024, "video/mp4"))


class CaptionScenarios(SimpleTestCase):
    def test_the_caption_joins_title_description_and_hashtags(self):
        self.assertEqual(draft("Title", "About", ("one", "two")).caption(), "Title\n\nAbout\n\n#one #two")

    def test_an_empty_part_leaves_no_blank_lines(self):
        self.assertEqual(draft("Title", "", ()).caption(), "Title")

    def test_surrounding_whitespace_is_trimmed(self):
        self.assertEqual(draft("  Title ", " About\n", ()).caption(), "Title\n\nAbout")
