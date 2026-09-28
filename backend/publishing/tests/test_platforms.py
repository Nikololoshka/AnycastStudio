import re
from pathlib import Path

from platforms.instagram.options import InstagramOptions
from platforms.tiktok.options import TikTokOptions
from platforms.x.options import XOptions
from platforms.youtube.options import YouTubeOptions

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


def frontend_defaults(module: str, constant: str, type_name: str) -> dict[str, str]:
    source = Path(__file__).resolve().parents[3] / f"frontend/src/platforms/{module}/settings.ts"
    block = re.search(rf"{constant}: {type_name} = \{{(.+?)\}};", source.read_text(), re.S).group(1)
    return dict(re.findall(r"(\w+):\s*'?([\w]+)'?,", block))


def backend_defaults(options) -> dict[str, str]:
    return {key: "null" if value is None else str(value) for key, value in options.as_json().items()}


class ContractScenarios(PublishingTestCase):
    # Given: the composer ships its own defaults so it can render before asking
    # the server. Then: they match, or a person sees one thing and gets another

    def assert_defaults_agree(self, frontend: dict[str, str], backend: dict[str, str]):
        self.assertEqual(set(frontend), set(backend))
        for key, value in frontend.items():
            self.assertEqual(backend[key].lower(), value.lower(), f"default for {key} differs")

    def test_the_youtube_defaults_match_the_browsers(self):
        frontend = frontend_defaults("youtube", "YOUTUBE_DEFAULT_SETTINGS", "YouTubeSettings")
        self.assert_defaults_agree(frontend, backend_defaults(YouTubeOptions.of({})))

    def test_the_tiktok_defaults_match_the_browsers(self):
        frontend = frontend_defaults("tiktok", "TIKTOK_DEFAULT_SETTINGS", "TikTokSettings")
        self.assert_defaults_agree(frontend, backend_defaults(TikTokOptions.of({})))

    def test_the_instagram_defaults_match_the_browsers(self):
        frontend = frontend_defaults("instagram", "INSTAGRAM_DEFAULT_SETTINGS", "InstagramSettings")
        self.assert_defaults_agree(frontend, backend_defaults(InstagramOptions.of({})))

    def test_the_x_defaults_match_the_browsers(self):
        frontend = frontend_defaults("x", "X_DEFAULT_SETTINGS", "XSettings")
        self.assert_defaults_agree(frontend, backend_defaults(XOptions.of({})))
