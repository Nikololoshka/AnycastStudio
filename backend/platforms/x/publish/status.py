from dataclasses import dataclass
from typing import Self

from ...core.errors import FailureType, PlatformError
from ...core.http import PlatformModel
from ...core.upload import TokenRejectionGuard
from ..client import XClient

PENDING = "pending"
IN_PROGRESS = "in_progress"
SUCCEEDED = "succeeded"
FAILED = "failed"


class ProcessingError(PlatformModel):
    message: str = ""
    name: str = ""

    @property
    def text(self) -> str:
        return self.message or self.name


class ProcessingInfo(PlatformModel):
    state: str = PENDING
    error: ProcessingError = ProcessingError()


class Media(PlatformModel):
    processing_info: ProcessingInfo | None = None


class MediaStatusAnswer(PlatformModel):
    data: Media = Media()


@dataclass(frozen=True)
class ProcessingStatus:
    state: str
    error: str = ""

    @classmethod
    def of(cls, answer: MediaStatusAnswer) -> Self:
        info = answer.data.processing_info
        if info is None:
            return cls(SUCCEEDED)
        return cls(state=info.state, error=info.error.text[:500])

    @property
    def is_ready(self) -> bool:
        return self.state == SUCCEEDED

    @property
    def is_failed(self) -> bool:
        return self.state == FAILED

    def failure(self) -> PlatformError:
        return PlatformError(FailureType.FILE, self.error or "X could not process the video", details=FAILED)


class MediaStatusApi:
    def __init__(self, client: XClient):
        self._client = client

    def fetch(self, access_token: str, media_id: str) -> ProcessingStatus:
        params = {"command": "STATUS", "media_id": media_id}
        response = TokenRejectionGuard().run(
            lambda: self._client.call("GET", "media/upload", access_token, params=params)
        )
        return ProcessingStatus.of(self._client.parse(response, MediaStatusAnswer))

    def status_of(self, body: dict) -> ProcessingStatus:
        return ProcessingStatus.of(self._client.parse_body(body, MediaStatusAnswer))
