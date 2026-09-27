import logging
import time
from dataclasses import dataclass

from django.conf import settings

from ..http import FILE, PLATFORM, VALIDATION, PlatformFailure
from .api import call, data_of, fresh_token_on_rejection
from .errors import Cancelled

MAX_SEGMENT_BYTES = 4 * 1024**2
MEDIA_LIFETIME_SECONDS = 23 * 60 * 60
MEDIA_CATEGORY = "tweet_video"

logger = logging.getLogger(__name__)


@dataclass
class ResumeState:
    media_id: str
    segment_bytes: int
    next_segment: int = 0
    created_at: float = 0

    def as_dict(self) -> dict:
        return {
            "media_id": self.media_id,
            "segment_bytes": self.segment_bytes,
            "next_segment": self.next_segment,
            "created_at": self.created_at,
        }

    @classmethod
    def of(cls, raw) -> "ResumeState | None":
        if not isinstance(raw, dict) or not raw.get("media_id") or not raw.get("segment_bytes"):
            return None
        return cls(
            media_id=str(raw["media_id"]),
            segment_bytes=int(raw["segment_bytes"]),
            next_segment=int(raw.get("next_segment", 0)),
            created_at=float(raw.get("created_at", 0)),
        )

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
    body = fresh_token_on_rejection(
        lambda: call(
            "POST",
            "media/upload/initialize",
            access_token,
            attempts=1,
            json={"media_type": mime_type, "total_bytes": size, "media_category": MEDIA_CATEGORY},
        )
    )
    media_id = data_of(body).get("id")
    if not media_id:
        raise PlatformFailure(PLATFORM, "X did not open an upload")
    return ResumeState(media_id=str(media_id), segment_bytes=segment_bytes(), created_at=time.time())


def _resumed(resume: ResumeState | None, size: int) -> ResumeState | None:
    if resume is None:
        return None
    if resume.expired:
        logger.info("X media %s is too old to finish, starting again", resume.media_id)
        return None
    resume.next_segment = min(resume.next_segment, resume.segment_count(size))
    return resume


def _send_segment(access_token: str, state: ResumeState, handle, size: int) -> None:
    offset = state.next_segment * state.segment_bytes
    length = min(state.segment_bytes, size - offset)
    handle.seek(offset)
    piece = handle.read(length)
    if len(piece) != length:
        raise PlatformFailure(FILE, "The video is shorter than it claimed to be")

    fresh_token_on_rejection(
        lambda: call(
            "POST",
            f"media/upload/{state.media_id}/append",
            access_token,
            data={"segment_index": str(state.next_segment)},
            files={"media": ("segment", piece, "application/octet-stream")},
        ),
        state,
    )


def finish(access_token: str, state: ResumeState) -> None:
    fresh_token_on_rejection(
        lambda: call("POST", f"media/upload/{state.media_id}/finalize", access_token, attempts=1), state
    )


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
        raise PlatformFailure(VALIDATION, "The video is empty")

    state = _resumed(resume, size) or start(access_token, size, mime_type)
    total = state.segment_count(size)

    with open(path, "rb") as handle:
        while state.next_segment < total:
            if should_cancel and should_cancel():
                raise Cancelled(state)

            _send_segment(access_token, state, handle, size)
            state.next_segment += 1
            if on_progress:
                on_progress(state.uploaded_bytes(size), size, state)

    finish(access_token, state)
    logger.info("Uploaded %d bytes to X as media %s", size, state.media_id)
    return state.media_id
