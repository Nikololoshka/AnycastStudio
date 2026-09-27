from dataclasses import dataclass

from ..http import FILE, PLATFORM, PlatformFailure
from ..upload import fresh_token_on_rejection
from .api import call

FINISHED = "FINISHED"
PUBLISHED = "PUBLISHED"
ERROR = "ERROR"
EXPIRED = "EXPIRED"

STATUS_FIELDS = "status_code,status,video_status"


@dataclass(frozen=True)
class ContainerStatus:
    status_code: str
    status: str = ""
    bytes_transferred: int | None = None

    @property
    def is_ready(self) -> bool:
        return self.status_code == FINISHED

    @property
    def is_published(self) -> bool:
        return self.status_code == PUBLISHED

    @property
    def is_dead(self) -> bool:
        return self.status_code in (ERROR, EXPIRED)


def _bytes_transferred(body: dict) -> int | None:
    video_status = body.get("video_status")
    phase = video_status.get("uploading_phase") if isinstance(video_status, dict) else None
    transferred = phase.get("bytes_transferred") if isinstance(phase, dict) else None
    if isinstance(transferred, bool) or not isinstance(transferred, (int, str)):
        return None
    return int(transferred) if str(transferred).isdigit() else None


def fetch_status(access_token: str, container_id: str, state=None) -> ContainerStatus:
    body = fresh_token_on_rejection(
        lambda: call("GET", container_id, access_token, params={"fields": STATUS_FIELDS}), state
    )
    return ContainerStatus(
        status_code=str(body.get("status_code") or ""),
        status=str(body.get("status") or ""),
        bytes_transferred=_bytes_transferred(body),
    )


def failure_of(status: ContainerStatus) -> PlatformFailure:
    if status.status_code == EXPIRED:
        return PlatformFailure(PLATFORM, "The Instagram upload expired before it was published", details=EXPIRED)
    return PlatformFailure(FILE, "Instagram could not process the video", details=status.status[:500] or ERROR)


def publish(access_token: str, ig_user_id: str, container_id: str) -> str:
    body = fresh_token_on_rejection(
        lambda: call(
            "POST", f"{ig_user_id}/media_publish", access_token, attempts=1, data={"creation_id": container_id}
        )
    )
    if not body.get("id"):
        raise PlatformFailure(PLATFORM, "Instagram did not say which post it published")
    return str(body["id"])


def post_url(access_token: str, media_id: str) -> str:
    body = call("GET", media_id, access_token, params={"fields": "permalink"})
    return str(body.get("permalink") or "")
