from dataclasses import dataclass

from ..core.errors import FailureType, PlatformError
from ..core.http import ResponseParser
from ..upload import fresh_token_on_rejection
from .client import LABEL, call, data_of
from .responses import Created, MediaStatusAnswer
from .video_options import VideoOptions

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


def _status(answer: MediaStatusAnswer) -> ProcessingStatus:
    info = answer.data.processing_info
    if info is None:
        return ProcessingStatus(SUCCEEDED)
    return ProcessingStatus(state=info.state, error=info.error.text[:500])


def status_of(body: dict) -> ProcessingStatus:
    return _status(ResponseParser(LABEL).parse_body(body, MediaStatusAnswer))


def fetch_status(access_token: str, media_id: str) -> ProcessingStatus:
    response = fresh_token_on_rejection(
        lambda: call("GET", "media/upload", access_token, params={"command": "STATUS", "media_id": media_id})
    )
    return _status(ResponseParser(LABEL).parse(response, MediaStatusAnswer))


def failure_of(status: ProcessingStatus) -> PlatformError:
    return PlatformError(FailureType.FILE, status.error or "X could not process the video", details=FAILED)


def create_post(access_token: str, text: str, media_id: str, options: VideoOptions) -> str:
    body = {"text": text, "media": {"media_ids": [media_id]}, **options.as_post_fields()}
    response = fresh_token_on_rejection(lambda: call("POST", "tweets", access_token, attempts=1, json=body))
    return data_of(response, Created, refusal="X did not say which post it created").id


def post_url(post_id: str) -> str:
    return POST_URL.format(post_id=post_id)
