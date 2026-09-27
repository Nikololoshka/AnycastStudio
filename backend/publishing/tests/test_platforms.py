from .base import PublishingTestCase


class PlatformScenarios(PublishingTestCase):
    def test_the_capabilities_are_served_to_the_browser(self):
        body = self.body(self.client.get("/api/platforms"))

        youtube = body["platforms"]["youtube"]
        self.assertEqual(youtube["label"], "YouTube")
        self.assertEqual(youtube["scheduling"], "native")
        self.assertIn("video/mp4", youtube["supportedMimeTypes"])

    def test_signing_in_is_required(self):
        self.client.logout()

        self.assertEqual(self.client.get("/api/platforms").status_code, 401)


class ContractScenarios(PublishingTestCase):
    def test_the_default_settings_match_the_browsers(self):
        # Given: the composer ships its own defaults so it can render before asking
        # the server. Then: they match, or a person sees one thing and gets another
        from pathlib import Path
        import re

        from platforms.youtube import video_options_of

        source = Path(__file__).resolve().parents[3] / "frontend/src/platforms/youtube/settings.ts"
        block = re.search(
            r"YOUTUBE_DEFAULT_SETTINGS: YouTubeSettings = \{(.+?)\};", source.read_text(), re.S
        ).group(1)

        frontend = dict(
            re.findall(r"(\w+):\s*'?([\w]+)'?,", block)
        )
        backend = {key: str(value) for key, value in video_options_of({}).as_json().items()}

        for key, value in frontend.items():
            self.assertEqual(
                backend[key].lower(), value.lower(), f"default for {key} differs"
            )
