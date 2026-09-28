import shutil
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, override_settings

from platforms.core.config import HttpConfig, PlatformConfig, UploadConfig

CHUNK = 1024
CONTENT = b"0123456789" * 512
SESSION_URI = "https://upload.googleapis.com/session/abc"
VIDEO_ID = "vid_abc123"

TEST_CONFIG = PlatformConfig(http=HttpConfig(attempts=3), upload=UploadConfig(chunk_bytes=CHUNK, stall_limit=3))


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}

    def json(self):
        return self._payload


def persisted(received: int) -> FakeResponse:
    if received == 0:
        return FakeResponse(308)
    return FakeResponse(308, headers={"Range": f"bytes=0-{received - 1}"})


@override_settings(PLATFORM_CHUNK_BYTES=CHUNK, UPLOAD_RETRY_ATTEMPTS=3)
class PlatformTestCase(SimpleTestCase):
    def setUp(self):
        patcher = mock.patch("platforms.core.http.transport.requests.request")
        self.http = patcher.start()
        self.addCleanup(patcher.stop)
        sleeper = mock.patch("platforms.core.http.retry.time.sleep")
        sleeper.start()
        self.addCleanup(sleeper.stop)

    def given_file(self, content: bytes = CONTENT) -> Path:
        folder = Path(tempfile.mkdtemp(prefix="anycast-platform-test-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        path = folder / "clip.mp4"
        path.write_bytes(content)
        return path

    def sent_ranges(self) -> list[str]:
        headers = [call.kwargs.get("headers", {}) for call in self.http.call_args_list]
        return [sent["Content-Range"] for sent in headers if "Content-Range" in sent]
