import shutil
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, mock

from platforms.core import PlatformType, PublishDraft, PublishJob, PublishMedia, UploadProgress

from .fakes.http import FakeAnswer, FakeSession

CHUNK = 1024
CONTENT = b"0123456789" * 512
REDIRECT = "http://localhost:5173/api/social/{platform}/callback"


class PlatformTestCase(IsolatedAsyncioTestCase):
    def setUp(self):
        self.http = FakeSession()
        sleeper = mock.patch("platforms.core.http.retry_policy.asyncio.sleep", new=mock.AsyncMock())
        sleeper.start()
        self.addCleanup(sleeper.stop)

    def given_answers(self, *answers) -> None:
        self.http.answer(*answers)

    def given_file(self, content: bytes = CONTENT) -> Path:
        folder = Path(tempfile.mkdtemp(prefix="anycast-platform-test-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        path = folder / "clip.mp4"
        path.write_bytes(content)
        return path

    def given_job(
        self,
        path: Path | None = None,
        *,
        size_bytes: int | None = None,
        title: str = "A title",
        description: str = "A description",
        hashtags: tuple[str, ...] = (),
        settings: dict | None = None,
        external_id: str = "external-1",
        media_id: str = "",
        duration_seconds: float | None = 10,
        mime_type: str = "video/mp4",
        **job_fields,
    ) -> PublishJob:
        path = path or self.given_file()
        size = size_bytes if size_bytes is not None else (path.stat().st_size if path.exists() else len(CONTENT))
        return PublishJob(
            target_id=1,
            platform=PlatformType.YOUTUBE,
            account_id=1,
            external_id=external_id,
            draft=PublishDraft(title, description, hashtags, settings or {}),
            media=PublishMedia(path, size, mime_type, duration_seconds),
            media_id=media_id,
            **job_fields,
        )

    @staticmethod
    async def drain(progress: AsyncGenerator[UploadProgress]) -> list[UploadProgress]:
        return [event async for event in progress]


def ok(body: dict | None = None) -> FakeAnswer:
    return FakeAnswer(200, body or {})
