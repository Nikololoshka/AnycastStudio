from dataclasses import dataclass

from ..http import FILE, PLATFORM, PlatformFailure
from .api import call, data_of, fresh_token_on_rejection
from .video_options import VideoOptions

PENDING = "pending"
IN_PROGRESS = "in_progress"
SUCCEEDED = "succeeded"
FAILED = "failed"

POST_URL = "https://x.com/i/web/status/{post_id}"


@dataclass(frozen=True)
class ProcessingStatus:
    state: str
    error: str = ""

    @property
    def is_ready(self) -> bool:
        return self.state == SUCCEEDED

    @property
    def is_failed(self) -> bool:
        return self.state == FAILED


def status_of(body: dict) -> ProcessingStatus:
    info = data_of(body).get("processing_info")
    if not isinstance(info, dict):
        return ProcessingStatus(SUCCEEDED)
    error = info.get("error")
    message = (error.get("message") or error.get("name")) if isinstance(error, dict) else ""
    return ProcessingStatus(state=str(info.get("state") or PENDING), error=str(message or "")[:500])


def fetch(access_token: str, media_id: str) -> ProcessingStatus:
    body = fresh_token_on_rejection(
        lambda: call("GET", "media/upload", access_token, params={"command": "STATUS", "media_id": media_id})
    )
    return status_of(body)


def failure_of(status: ProcessingStatus) -> PlatformFailure:
    return PlatformFailure(FILE, status.error or "X could not process the video", details=FAILED)


def create_post(access_token: str, text: str, media_id: str, options: VideoOptions) -> str:
    body = {"text": text, "media": {"media_ids": [media_id]}, **options.as_post_fields()}
    answer = fresh_token_on_rejection(lambda: call("POST", "tweets", access_token, attempts=1, json=body))
    post_id = data_of(answer).get("id")
    if not post_id:
        raise PlatformFailure(PLATFORM, "X did not say which post it created")
    return str(post_id)


def post_url(post_id: str) -> str:
    return POST_URL.format(post_id=post_id)
