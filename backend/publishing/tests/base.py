import json
import shutil
import tempfile
from unittest import mock

import httplib2
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from googleapiclient.discovery import build

from accounts.models import User
from config.wiring import Container, container
from media import storage
from media.models import MediaAsset
from platforms2.tests.fakes.http import FakeSession
from platforms2.youtube.publish.youtube_api import YouTubeApi
from publishing.models import Publication, PublicationTarget
from social.models import SocialAccount

CREATE_URL = "/api/publications/create"
LIST_URL = "/api/publications"

EMAIL = "person@example.com"
PASSWORD = "correct-horse-battery"

CONTENT = b"0123456789" * 512
CHUNK = 1024
VIDEO_ID = "vid_abc123"
SESSION_URI = "https://upload.googleapis.com/session/abc"


class GoogleDouble:
    def __init__(self, size: int, fail_at: int | None = None, failure=None, fail_always: bool = False):
        self.size = size
        self.received = 0
        self.chunks: list[bytes] = []
        self.ranges: list[str] = []
        self.inserted: list[dict] = []
        self.published: list[dict] = []
        self.tokens: list[str] = []
        self.fail_at = fail_at
        self.fail_always = fail_always
        self.failure = failure or (500, {"error": {"code": 500, "message": "boom"}})
        self.session_calls = 0

    def videos(self, api: YouTubeApi, access_token: str):
        self.tokens.append(access_token)
        return build("youtube", "v3", http=self, static_discovery=True, cache_discovery=False).videos()

    def request(self, uri, method="GET", body=None, headers=None, redirections=1, connection_type=None):
        if self.fail_always:
            return self._answer(*self.failure)

        if "upload/youtube" in uri:
            self.session_calls += 1
            self.received = 0
            self.inserted.append(json.loads(body))
            return httplib2.Response({"status": "200", "location": SESSION_URI}), b""

        if uri == SESSION_URI:
            self.ranges.append(headers["Content-Range"])
            if self.fail_at is not None and self.received == self.fail_at:
                self.fail_at = None
                return self._answer(*self.failure)
            self.chunks.append(body)
            self.received += len(body)
            if self.received >= self.size:
                return self._answer(200, {"id": VIDEO_ID})
            return httplib2.Response({"status": "308", "range": f"bytes=0-{self.received - 1}"}), b""

        if "youtube/v3/videos" in uri:
            self.published.append(json.loads(body))
            return self._answer(200, {"id": VIDEO_ID})

        raise AssertionError(f"unexpected call to {uri}")

    @staticmethod
    def _answer(status: int, payload: dict):
        return httplib2.Response({"status": str(status)}), json.dumps(payload).encode()


class PublishingTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_root = tempfile.mkdtemp(prefix="anycast-publish-test-")
        cls.override = override_settings(
            MEDIA_ROOT=cls.media_root,
            PLATFORM_CHUNK_BYTES=CHUNK,
            UPLOAD_RETRY_ATTEMPTS=3,
        )
        cls.override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.override.disable()
        shutil.rmtree(cls.media_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(EMAIL, PASSWORD)
        self.client.force_login(self.user)
        self.account = self.given_connected_account()
        self.asset = self.given_uploaded_asset()

        self.http = FakeSession()
        self.patch(mock.patch.object(Container, "open_session", return_value=self.http))
        self.patch(mock.patch("platforms2.core.http.retry_policy.asyncio.sleep", new=mock.AsyncMock()))
        self.patch(mock.patch("googleapiclient.http.time.sleep"))

    def patch(self, patcher):
        started = patcher.start()
        self.addCleanup(patcher.stop)
        return started

    def given_connected_account(self) -> SocialAccount:
        return SocialAccount.objects.create(
            user=self.user,
            platform="youtube",
            external_id="UC_channel",
            display_name="A Channel",
            access_token="ya29.token",
            refresh_token="1//refresh",
            token_expires_at=timezone.now() + timezone.timedelta(hours=1),
        )

    def given_uploaded_asset(self, content=CONTENT) -> MediaAsset:
        asset = MediaAsset.objects.create(
            user=self.user,
            filename="clip.mp4",
            mime_type="video/mp4",
            size_bytes=len(content),
            storage_path="",
            status=MediaAsset.Status.READY,
        )
        asset.storage_path = storage.asset_path(self.user.pk, asset.pk, "clip.mp4")
        path = storage.absolute(asset.storage_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        asset.save(update_fields=["storage_path"])
        return asset

    def given_google(self, **kwargs) -> GoogleDouble:
        double = GoogleDouble(size=self.asset.size_bytes, **kwargs)
        self.patch(mock.patch.object(YouTubeApi, "videos", new=lambda api, token: double.videos(api, token)))
        return double

    def given_answers(self, *answers) -> None:
        self.http.answer_only(*answers)

    def run_target(self, target_id: int):
        return container().run(lambda services: services.pipeline.run(target_id))

    def confirm_target(self, target_id: int):
        return container().run(lambda services: services.confirmations.confirm(target_id))

    def body(self, response) -> dict:
        return json.loads(response.content)

    def create_publication(self, **overrides):
        payload = {
            "mediaAssetId": self.asset.pk,
            "title": "A video",
            "description": "About things",
            "hashtags": ["one", "two"],
            "targets": [
                {
                    "platform": "youtube",
                    "socialAccountId": self.account.pk,
                    "settings": {"privacyStatus": "public"},
                }
            ],
        }
        payload.update(overrides)
        return self.client.post(CREATE_URL, data=json.dumps(payload), content_type="application/json")

    def only_target(self) -> PublicationTarget:
        return PublicationTarget.objects.get()

    def only_publication(self) -> Publication:
        return Publication.objects.get()
