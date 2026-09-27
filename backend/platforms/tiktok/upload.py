import logging
import time
from dataclasses import dataclass

from django.conf import settings

from ..http import AUTHENTICATION, FILE, PLATFORM, PlatformFailure
from .api import API_ROOT, call, send
from .errors import Cancelled, NeedsFreshToken

INIT_ENDPOINT = f"{API_ROOT}/post/publish/video/init/"

UPLOAD_URL_LIFETIME_SECONDS = 55 * 60

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PostInfo:
    title: str
    privacy_level: str
    disable_comment: bool
    disable_duet: bool
    disable_stitch: bool
    brand_content_toggle: bool
    brand_organic_toggle: bool
    is_aigc: bool
    video_cover_timestamp_ms: int | None = None

    def as_body(self) -> dict:
        body = {
            "title": self.title,
            "privacy_level": self.privacy_level,
            "disable_comment": self.disable_comment,
            "disable_duet": self.disable_duet,
            "disable_stitch": self.disable_stitch,
            "brand_content_toggle": self.brand_content_toggle,
            "brand_organic_toggle": self.brand_organic_toggle,
            "is_aigc": self.is_aigc,
        }
        if self.video_cover_timestamp_ms is not None:
            body["video_cover_timestamp_ms"] = self.video_cover_timestamp_ms
        return body


@dataclass
class ResumeState:
    publish_id: str
    upload_url: str
    chunk_size: int
    total_chunks: int
    next_chunk: int = 0
    expires_at: float = 0

    def as_dict(self) -> dict:
        return {
            "publish_id": self.publish_id,
            "upload_url": self.upload_url,
            "chunk_size": self.chunk_size,
            "total_chunks": self.total_chunks,
            "next_chunk": self.next_chunk,
            "expires_at": self.expires_at,
        }

    @classmethod
    def of(cls, raw) -> "ResumeState | None":
        if not isinstance(raw, dict) or not raw.get("publish_id") or not raw.get("upload_url"):
            return None
        return cls(
            publish_id=str(raw["publish_id"]),
            upload_url=str(raw["upload_url"]),
            chunk_size=int(raw["chunk_size"]),
            total_chunks=int(raw["total_chunks"]),
            next_chunk=int(raw.get("next_chunk", 0)),
            expires_at=float(raw.get("expires_at", 0)),
        )

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at

    def uploaded_bytes(self, size: int) -> int:
        return min(self.next_chunk * self.chunk_size, size)

    def bounds_of(self, index: int, size: int) -> tuple[int, int]:
        start = index * self.chunk_size
        end = size - 1 if index == self.total_chunks - 1 else start + self.chunk_size - 1
        return start, end


def chunk_plan(size: int, preferred: int) -> tuple[int, int]:
    chunk_size = max(1, min(size, preferred))
    return chunk_size, max(1, size // chunk_size)


def start(access_token: str, post_info: PostInfo, size: int) -> ResumeState:
    chunk_size, total_chunks = chunk_plan(size, settings.PLATFORM_CHUNK_BYTES)
    body = {
        "post_info": post_info.as_body(),
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": size,
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunks,
        },
    }
    try:
        data = call("POST", INIT_ENDPOINT, access_token, json=body)
    except PlatformFailure as failure:
        if failure.type == AUTHENTICATION:
            raise NeedsFreshToken(None, failure.message) from None
        raise

    if not data.get("publish_id") or not data.get("upload_url"):
        raise PlatformFailure(PLATFORM, "TikTok did not open an upload")

    return ResumeState(
        publish_id=str(data["publish_id"]),
        upload_url=str(data["upload_url"]),
        chunk_size=chunk_size,
        total_chunks=total_chunks,
        expires_at=time.time() + UPLOAD_URL_LIFETIME_SECONDS,
    )


def _send_chunk(state: ResumeState, handle, size: int, mime_type: str):
    first, last = state.bounds_of(state.next_chunk, size)
    handle.seek(first)
    piece = handle.read(last - first + 1)
    if len(piece) != last - first + 1:
        raise PlatformFailure(FILE, "The video is shorter than it claimed to be")

    headers = {"Content-Type": mime_type, "Content-Range": f"bytes {first}-{last}/{size}"}
    return send("PUT", state.upload_url, headers=headers, data=piece)


def upload(
    *,
    path,
    size: int,
    mime_type: str,
    post_info: PostInfo,
    access_token: str,
    resume: ResumeState | None = None,
    on_progress=None,
    should_cancel=None,
) -> str:
    if resume is not None and not resume.expired:
        state = resume
    else:
        if resume is not None:
            logger.info("TikTok upload %s outlived its upload URL, starting again", resume.publish_id)
        state = start(access_token, post_info, size)

    with open(path, "rb") as handle:
        while state.next_chunk < state.total_chunks:
            if should_cancel and should_cancel():
                raise Cancelled(state)

            response = _send_chunk(state, handle, size, mime_type)
            is_last = state.next_chunk == state.total_chunks - 1
            if is_last and response.status_code != 201:
                raise PlatformFailure(PLATFORM, f"TikTok answered HTTP {response.status_code} to the last chunk")

            state.next_chunk += 1
            if on_progress:
                on_progress(state.uploaded_bytes(size), size, state)

    logger.info("Uploaded %d bytes to TikTok as %s", size, state.publish_id)
    return state.publish_id
