from ..core.errors import FailureType, PlatformError
from ..upload import fresh_token_on_rejection
from .client import call
from .responses import ERROR, EXPIRED, ContainerStatus, Created, Permalink

STATUS_FIELDS = "status_code,status,video_status"


def fetch_status(access_token: str, container_id: str, state=None) -> ContainerStatus:
    return fresh_token_on_rejection(
        lambda: call("GET", container_id, access_token, ContainerStatus, params={"fields": STATUS_FIELDS}), state
    )


def failure_of(status: ContainerStatus) -> PlatformError:
    if status.status_code == EXPIRED:
        return PlatformError(FailureType.PLATFORM, "The Instagram upload expired before it was published", details=EXPIRED)
    return PlatformError(FailureType.FILE, "Instagram could not process the video", details=status.status[:500] or ERROR)


def publish(access_token: str, ig_user_id: str, container_id: str) -> str:
    published = fresh_token_on_rejection(
        lambda: call(
            "POST",
            f"{ig_user_id}/media_publish",
            access_token,
            Created,
            refusal="Instagram did not say which post it published",
            attempts=1,
            data={"creation_id": container_id},
        )
    )
    return published.id


def post_url(access_token: str, media_id: str) -> str:
    return call("GET", media_id, access_token, Permalink, params={"fields": "permalink"}).permalink
