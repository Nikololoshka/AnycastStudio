from typing import Annotated

from pydantic import BeforeValidator

from ...core.errors import FailureType, PlatformError
from ...core.http import PlatformModel
from ...core.upload import ResumableState, TokenRejectionGuard
from ..client import InstagramClient
from ..responses import Created

FINISHED = "FINISHED"
PUBLISHED = "PUBLISHED"
ERROR = "ERROR"
EXPIRED = "EXPIRED"

STATUS_FIELDS = "status_code,status,video_status"


def _count(value) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    return int(value) if str(value).isdigit() else None


Count = Annotated[int | None, BeforeValidator(_count)]


class UploadingPhase(PlatformModel):
    bytes_transferred: Count = None


class VideoStatus(PlatformModel):
    uploading_phase: UploadingPhase = UploadingPhase()


class ContainerStatus(PlatformModel):
    status_code: str = ""
    status: str = ""
    video_status: VideoStatus = VideoStatus()

    @property
    def bytes_transferred(self) -> int | None:
        return self.video_status.uploading_phase.bytes_transferred

    @property
    def is_ready(self) -> bool:
        return self.status_code == FINISHED

    @property
    def is_published(self) -> bool:
        return self.status_code == PUBLISHED

    @property
    def is_dead(self) -> bool:
        return self.status_code in (ERROR, EXPIRED)

    def failure(self) -> PlatformError:
        if self.status_code == EXPIRED:
            message = "The Instagram upload expired before it was published"
            return PlatformError(FailureType.PLATFORM, message, details=EXPIRED)
        details = self.status[:500] or ERROR
        return PlatformError(FailureType.FILE, "Instagram could not process the video", details=details)


class Permalink(PlatformModel):
    permalink: str = ""


class ContainerApi:
    def __init__(self, client: InstagramClient):
        self._client = client

    def status(self, access_token: str, container_id: str, state: ResumableState | None = None) -> ContainerStatus:
        params = {"fields": STATUS_FIELDS}
        return TokenRejectionGuard(state).run(
            lambda: self._client.call("GET", container_id, access_token, ContainerStatus, params=params)
        )

    def publish(self, access_token: str, ig_user_id: str, container_id: str) -> str:
        refusal = "Instagram did not say which post it published"
        published = TokenRejectionGuard().run(
            lambda: self._client.call(
                "POST",
                f"{ig_user_id}/media_publish",
                access_token,
                Created,
                refusal=refusal,
                attempts=1,
                data={"creation_id": container_id},
            )
        )
        return published.id

    def post_url(self, access_token: str, media_id: str) -> str:
        params = {"fields": "permalink"}
        return self._client.call("GET", media_id, access_token, Permalink, params=params).permalink
