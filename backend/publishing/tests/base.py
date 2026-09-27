"""Shared setup for the publishing scenarios.

Google is mocked at the HTTP layer, so the real chunking, the real offsets and
the real retry policy all run.
"""

import json
import shutil
import tempfile
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from media import storage
from media.models import MediaAsset
from publishing.models import Publication, PublicationTarget
from social.models import SocialAccount

CREATE_URL = "/api/publications/create"
LIST_URL = "/api/publications"

EMAIL = "person@example.com"
PASSWORD = "correct-horse-battery"

CONTENT = b"0123456789" * 512  # 5120 bytes
CHUNK = 1024
VIDEO_ID = "vid_abc123"
SESSION_URI = "https://upload.googleapis.com/session/abc"


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class GoogleDouble:
    """Answers the upload protocol the way Google does, and records what it saw."""

    def __init__(self, size: int, fail_at: int | None = None, failure=None):
        self.size = size
        self.received = 0
        self.chunks: list[bytes] = []
        self.ranges: list[str] = []
        self.published: list[dict] = []
        self.fail_at = fail_at
        self.failure = failure or FakeResponse(500, {"error": {"message": "boom"}})
        self.session_calls = 0
        self.progress_queries = 0

    def progress(self) -> "FakeResponse":
        if self.received >= self.size:
            return FakeResponse(200, {"id": VIDEO_ID})
        if self.received == 0:
            return FakeResponse(308, {})
        return FakeResponse(308, {}, {"Range": f"bytes=0-{self.received - 1}"})

    def __call__(self, method, url, **kwargs):
        if "upload/youtube" in url:
            self.session_calls += 1
            return FakeResponse(200, {}, {"Location": SESSION_URI})

        if url == SESSION_URI and kwargs["headers"]["Content-Range"].startswith("bytes */"):
            self.progress_queries += 1
            return self.progress()
        if url == SESSION_URI:
            body = kwargs.get("data") or b""
            self.ranges.append(kwargs["headers"]["Content-Range"])

            if self.fail_at is not None and self.received == self.fail_at:
                self.fail_at = None  # fail once, then behave
                return self.failure

            self.chunks.append(body)
            self.received += len(body)

            if self.received >= self.size:
                return FakeResponse(200, {"id": VIDEO_ID})
            return FakeResponse(
                308, {}, {"Range": f"bytes=0-{self.received - 1}"}
            )

        if "youtube/v3/videos" in url:
            self.published.append(kwargs.get("json") or {})
            return FakeResponse(200, {"id": VIDEO_ID})

        raise AssertionError(f"unexpected call to {url}")


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

        patcher = mock.patch("platforms.http.transport.requests.request")
        self.http = patcher.start()
        self.addCleanup(patcher.stop)
        # Nothing here sleeps for real; the backoff is the policy, not the wait.
        sleeper = mock.patch("platforms.http.retry.time.sleep")
        sleeper.start()
        self.addCleanup(sleeper.stop)

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
        self.http.side_effect = double
        return double

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
        # Dispatch happens on commit, which a TestCase never reaches on its own.
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                CREATE_URL, data=json.dumps(payload), content_type="application/json"
            )

    def only_target(self) -> PublicationTarget:
        return PublicationTarget.objects.get()

    def only_publication(self) -> Publication:
        return Publication.objects.get()
