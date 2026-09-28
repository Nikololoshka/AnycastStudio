import logging
import time
from dataclasses import dataclass

from django.conf import settings

from ..core.errors import FailureType, PlatformError
from ..core.http import ResponseParser
from ..upload import ResumableState, drive, fresh_token_on_rejection, read_piece
from .client import LABEL, RUPLOAD_ROOT, authorization, call, send
from .responses import Chunk, Created
from .status import fetch_status

CONTAINER_LIFETIME_SECONDS = 23 * 60 * 60

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReelInfo:
    caption: str
    share_to_feed: bool
    thumb_offset_ms: int

    def as_form(self) -> dict:
        return {
            "media_type": "REELS",
            "upload_type": "resumable",
            "caption": self.caption,
            "share_to_feed": "true" if self.share_to_feed else "false",
            "thumb_offset": str(self.thumb_offset_ms),
        }


@dataclass
class ResumeState(ResumableState):
    container_id: str
    offset: int = 0
    created_at: float = 0

    @property
    def expired(self) -> bool:
        return time.time() - self.created_at >= CONTAINER_LIFETIME_SECONDS


def start(access_token: str, ig_user_id: str, reel: ReelInfo) -> ResumeState:
    container = fresh_token_on_rejection(
        lambda: call(
            "POST",
            f"{ig_user_id}/media",
            access_token,
            Created,
            refusal="Instagram did not open an upload",
            attempts=1,
            data=reel.as_form(),
        )
    )
    return ResumeState(container_id=container.id, created_at=time.time())


def _resumed(access_token: str, resume: ResumeState | None, size: int) -> ResumeState | None:
    if resume is None:
        return None
    if resume.expired:
        logger.info("Instagram container %s is too old to finish, starting again", resume.container_id)
        return None

    status = fetch_status(access_token, resume.container_id, resume)
    if status.is_dead or status.is_published:
        logger.info("Instagram container %s is %s, starting again", resume.container_id, status.status_code)
        return None
    if status.bytes_transferred is not None:
        resume.offset = min(status.bytes_transferred, size)
    return resume


@dataclass
class Session:
    state: ResumeState
    size: int
    access_token: str

    @property
    def done(self) -> bool:
        return self.state.offset >= self.size

    @property
    def uploaded(self) -> int:
        return self.state.offset

    def send_next(self, handle) -> None:
        length = min(settings.PLATFORM_CHUNK_BYTES, self.size - self.state.offset)
        piece = read_piece(handle, self.state.offset, length)
        headers = {**authorization(self.access_token), "offset": str(self.state.offset), "file_size": str(self.size)}
        response = fresh_token_on_rejection(
            lambda: send("POST", f"{RUPLOAD_ROOT}/{self.state.container_id}", headers=headers, data=piece), self.state
        )
        refusal = "Instagram did not accept a piece of the video"
        if not ResponseParser(LABEL).parse(response, Chunk, refusal=refusal).success:
            raise PlatformError(FailureType.PLATFORM, refusal)
        self.state.offset += length

    def finish(self) -> str:
        logger.info("Uploaded %d bytes to Instagram as container %s", self.size, self.state.container_id)
        return self.state.container_id


def upload(
    *,
    path,
    size: int,
    ig_user_id: str,
    reel: ReelInfo,
    access_token: str,
    resume: ResumeState | None = None,
    on_progress=None,
    should_cancel=None,
) -> str:
    if size <= 0:
        raise PlatformError(FailureType.VALIDATION, "The video is empty")

    state = _resumed(access_token, resume, size) or start(access_token, ig_user_id, reel)
    session = Session(state, size, access_token)
    return drive(session, path=path, size=size, on_progress=on_progress, should_cancel=should_cancel)
