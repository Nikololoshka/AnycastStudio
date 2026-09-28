import logging
import time
from dataclasses import dataclass

from django.conf import settings

from ..core.errors import FailureType, PlatformError
from ..core.upload import ResumableState, TokenRejectionGuard, UploadDriver, UploadSession, VideoFile
from .client import API_ROOT, call, send
from .responses import InitData

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
class ResumeState(ResumableState):
    publish_id: str
    upload_url: str
    chunk_size: int
    total_chunks: int
    next_chunk: int = 0
    expires_at: float = 0

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
    data = TokenRejectionGuard().run(
        lambda: call("POST", INIT_ENDPOINT, access_token, InitData, refusal="TikTok did not open an upload", json=body)
    )

    return ResumeState(
        publish_id=data.publish_id,
        upload_url=data.upload_url,
        chunk_size=chunk_size,
        total_chunks=total_chunks,
        expires_at=time.time() + UPLOAD_URL_LIFETIME_SECONDS,
    )


@dataclass
class Session(UploadSession):
    state: ResumeState
    size: int
    mime_type: str

    @property
    def done(self) -> bool:
        return self.state.next_chunk >= self.state.total_chunks

    @property
    def uploaded(self) -> int:
        return self.state.uploaded_bytes(self.size)

    def send_next(self, video: VideoFile) -> None:
        first, last = self.state.bounds_of(self.state.next_chunk, self.size)
        piece = video.piece(first, last - first + 1)
        headers = {"Content-Type": self.mime_type, "Content-Range": f"bytes {first}-{last}/{self.size}"}
        response = send("PUT", self.state.upload_url, headers=headers, data=piece)

        is_last = self.state.next_chunk == self.state.total_chunks - 1
        if is_last and response.status_code != 201:
            raise PlatformError(FailureType.PLATFORM, f"TikTok answered HTTP {response.status_code} to the last chunk")
        self.state.next_chunk += 1

    def finish(self) -> str:
        logger.info("Uploaded %d bytes to TikTok as %s", self.size, self.state.publish_id)
        return self.state.publish_id


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

    session = Session(state, size, mime_type)
    return UploadDriver(on_progress, should_cancel).drive(session, path=path, size=size)
