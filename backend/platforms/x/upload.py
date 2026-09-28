import logging
import time
from dataclasses import dataclass

from django.conf import settings

from ..core.errors import FailureType, PlatformError
from ..upload import ResumableState, drive, fresh_token_on_rejection, read_piece
from .client import call, data_of
from .responses import Created

MAX_SEGMENT_BYTES = 4 * 1024**2
MEDIA_LIFETIME_SECONDS = 23 * 60 * 60
MEDIA_CATEGORY = "tweet_video"

logger = logging.getLogger(__name__)


@dataclass
class ResumeState(ResumableState):
    media_id: str
    segment_bytes: int
    next_segment: int = 0
    created_at: float = 0

    @property
    def expired(self) -> bool:
        return time.time() - self.created_at >= MEDIA_LIFETIME_SECONDS

    def uploaded_bytes(self, size: int) -> int:
        return min(self.next_segment * self.segment_bytes, size)

    def segment_count(self, size: int) -> int:
        return -(-size // self.segment_bytes)


def segment_bytes() -> int:
    return min(settings.PLATFORM_CHUNK_BYTES, MAX_SEGMENT_BYTES)


def start(access_token: str, size: int, mime_type: str) -> ResumeState:
    response = fresh_token_on_rejection(
        lambda: call(
            "POST",
            "media/upload/initialize",
            access_token,
            attempts=1,
            json={"media_type": mime_type, "total_bytes": size, "media_category": MEDIA_CATEGORY},
        )
    )
    media = data_of(response, Created, refusal="X did not open an upload")
    return ResumeState(media_id=media.id, segment_bytes=segment_bytes(), created_at=time.time())


def _resumed(resume: ResumeState | None, size: int) -> ResumeState | None:
    if resume is None:
        return None
    if resume.expired:
        logger.info("X media %s is too old to finish, starting again", resume.media_id)
        return None
    resume.next_segment = min(resume.next_segment, resume.segment_count(size))
    return resume


def finalize(access_token: str, state: ResumeState) -> None:
    fresh_token_on_rejection(
        lambda: call("POST", f"media/upload/{state.media_id}/finalize", access_token, attempts=1), state
    )


@dataclass
class Session:
    state: ResumeState
    size: int
    access_token: str

    @property
    def done(self) -> bool:
        return self.state.next_segment >= self.state.segment_count(self.size)

    @property
    def uploaded(self) -> int:
        return self.state.uploaded_bytes(self.size)

    def send_next(self, handle) -> None:
        offset = self.state.next_segment * self.state.segment_bytes
        piece = read_piece(handle, offset, min(self.state.segment_bytes, self.size - offset))
        fresh_token_on_rejection(
            lambda: call(
                "POST",
                f"media/upload/{self.state.media_id}/append",
                self.access_token,
                data={"segment_index": str(self.state.next_segment)},
                files={"media": ("segment", piece, "application/octet-stream")},
            ),
            self.state,
        )
        self.state.next_segment += 1

    def finish(self) -> str:
        finalize(self.access_token, self.state)
        logger.info("Uploaded %d bytes to X as media %s", self.size, self.state.media_id)
        return self.state.media_id


def upload(
    *,
    path,
    size: int,
    mime_type: str,
    access_token: str,
    resume: ResumeState | None = None,
    on_progress=None,
    should_cancel=None,
) -> str:
    if size <= 0:
        raise PlatformError(FailureType.VALIDATION, "The video is empty")

    state = _resumed(resume, size) or start(access_token, size, mime_type)
    session = Session(state, size, access_token)
    return drive(session, path=path, size=size, on_progress=on_progress, should_cancel=should_cancel)
