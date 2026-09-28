import logging
import re
from dataclasses import dataclass

from django.conf import settings

from ..core.errors import FailureType, PlatformError
from ..core.http import ResponseParser
from ..upload import ResumableState, drive, fresh_token_on_rejection, read_piece
from .client import LABEL, bearer, send
from .responses import UploadedVideo

UPLOAD_ENDPOINT = "https://www.googleapis.com/upload/youtube/v3/videos"

RANGE_PATTERN = re.compile(r"bytes=0-(\d+)")

logger = logging.getLogger(__name__)


@dataclass
class ResumeState(ResumableState):
    session_uri: str
    offset: int = 0


@dataclass
class VideoMetadata:
    title: str
    description: str
    tags: list[str]
    privacy_status: str
    category_id: str
    license: str
    embeddable: bool
    public_stats_viewable: bool
    made_for_kids: bool
    contains_synthetic_media: bool
    notify_subscribers: bool

    def as_body(self) -> dict:
        return {
            "snippet": {
                "title": self.title,
                "description": self.description,
                "tags": self.tags,
                "categoryId": self.category_id,
            },
            "status": {
                "privacyStatus": self.privacy_status,
                "license": self.license,
                "embeddable": self.embeddable,
                "publicStatsViewable": self.public_stats_viewable,
                "selfDeclaredMadeForKids": self.made_for_kids,
                "containsSyntheticMedia": self.contains_synthetic_media,
            },
        }


def start_session(access_token: str, metadata: VideoMetadata, size: int, mime_type: str) -> str:
    params = {
        "uploadType": "resumable",
        "part": "snippet,status",
        "notifySubscribers": str(metadata.notify_subscribers).lower(),
    }
    headers = {
        **bearer(access_token),
        "X-Upload-Content-Type": mime_type,
        "X-Upload-Content-Length": str(size),
    }

    response = send("POST", UPLOAD_ENDPOINT, params=params, headers=headers, json=metadata.as_body())

    location = response.headers.get("Location")
    if not location:
        raise PlatformError(FailureType.PLATFORM, "YouTube did not open an upload session")
    return location


def persisted_offset(response) -> int:
    match = RANGE_PATTERN.search(response.headers.get("Range", ""))
    return int(match.group(1)) + 1 if match else 0


def _is_complete(response) -> bool:
    return response.status_code in (200, 201)


def _put(state: ResumeState, headers: dict, body: bytes = b""):
    return fresh_token_on_rejection(lambda: send("PUT", state.session_uri, headers=headers, data=body), state)


def _ask_progress(state: ResumeState, size: int):
    return _put(state, {"Content-Range": f"bytes */{size}"})


def _send_piece(state: ResumeState, piece: bytes, size: int, mime_type: str):
    last = state.offset + len(piece) - 1
    headers = {"Content-Range": f"bytes {state.offset}-{last}/{size}", "Content-Type": mime_type}
    return _put(state, headers, piece)


def _video_id(response, size: int) -> str:
    video = ResponseParser(LABEL).parse(response, UploadedVideo, refusal="YouTube accepted the file but returned no video id")
    logger.info("Uploaded %d bytes to YouTube as %s", size, video.id)
    return video.id


@dataclass
class Session:
    state: ResumeState
    size: int
    mime_type: str
    video_id: str | None = None
    chunks_without_progress: int = 0

    @property
    def done(self) -> bool:
        return self.video_id is not None

    @property
    def uploaded(self) -> int:
        return self.state.offset

    def send_next(self, handle) -> None:
        length = min(settings.PLATFORM_CHUNK_BYTES, self.size - self.state.offset)
        piece = read_piece(handle, self.state.offset, length)
        response = _send_piece(self.state, piece, self.size, self.mime_type)
        if _is_complete(response):
            self.state.offset = self.size
            self.video_id = _video_id(response, self.size)
            return

        previous = self.state.offset
        self.state.offset = persisted_offset(response)
        self.chunks_without_progress = self.chunks_without_progress + 1 if self.state.offset <= previous else 0
        if self.chunks_without_progress >= settings.UPLOAD_RETRY_ATTEMPTS:
            raise PlatformError(FailureType.PLATFORM, "YouTube stopped accepting the upload")

    def finish(self) -> str:
        return self.video_id or ""


def _session(
    access_token: str, metadata: VideoMetadata, size: int, mime_type: str, resume: ResumeState | None
) -> Session:
    if resume is None:
        state = ResumeState(session_uri=start_session(access_token, metadata, size, mime_type))
        return Session(state, size, mime_type)

    progress = _ask_progress(resume, size)
    if _is_complete(progress):
        return Session(resume, size, mime_type, video_id=_video_id(progress, size))
    resume.offset = persisted_offset(progress)
    return Session(resume, size, mime_type)


def upload(
    *,
    path,
    size: int,
    mime_type: str,
    metadata: VideoMetadata,
    access_token: str,
    resume: ResumeState | None = None,
    on_progress=None,
    should_cancel=None,
) -> str:
    session = _session(access_token, metadata, size, mime_type, resume)
    return drive(session, path=path, size=size, on_progress=on_progress, should_cancel=should_cancel)
