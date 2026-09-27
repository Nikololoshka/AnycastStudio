import logging
import re
from dataclasses import dataclass

from django.conf import settings

from ..http import FILE, PLATFORM, PlatformFailure, json_dict
from ..upload import UploadCancelled, fresh_token_on_rejection
from .api import bearer, send

UPLOAD_ENDPOINT = "https://www.googleapis.com/upload/youtube/v3/videos"

RANGE_PATTERN = re.compile(r"bytes=0-(\d+)")

logger = logging.getLogger(__name__)


@dataclass
class ResumeState:
    session_uri: str
    offset: int = 0

    def as_dict(self) -> dict:
        return {"session_uri": self.session_uri, "offset": self.offset}

    @classmethod
    def of(cls, raw) -> "ResumeState | None":
        if not isinstance(raw, dict) or not raw.get("session_uri"):
            return None
        return cls(session_uri=raw["session_uri"], offset=int(raw.get("offset", 0)))


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
        raise PlatformFailure(PLATFORM, "YouTube did not open an upload session")
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
    video_id = json_dict(response).get("id")
    if not video_id:
        raise PlatformFailure(PLATFORM, "YouTube accepted the file but returned no video id")
    logger.info("Uploaded %d bytes to YouTube as %s", size, video_id)
    return str(video_id)


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
    if resume is None:
        state = ResumeState(session_uri=start_session(access_token, metadata, size, mime_type))
    else:
        state = resume
        progress = _ask_progress(state, size)
        if _is_complete(progress):
            return _video_id(progress, size)
        state.offset = persisted_offset(progress)

    chunk_size = settings.PLATFORM_CHUNK_BYTES
    chunks_without_progress = 0

    with open(path, "rb") as handle:
        while True:
            if should_cancel and should_cancel():
                raise UploadCancelled(state.as_dict())

            handle.seek(state.offset)
            piece = handle.read(chunk_size)
            if not piece:
                raise PlatformFailure(FILE, "The video is shorter than it claimed to be")

            response = _send_piece(state, piece, size, mime_type)
            if _is_complete(response):
                state.offset = size
                if on_progress:
                    on_progress(size, size, state)
                return _video_id(response, size)

            previous = state.offset
            state.offset = persisted_offset(response)
            chunks_without_progress = chunks_without_progress + 1 if state.offset <= previous else 0
            if chunks_without_progress >= settings.UPLOAD_RETRY_ATTEMPTS:
                raise PlatformFailure(PLATFORM, "YouTube stopped accepting the upload")

            if on_progress:
                on_progress(state.offset, size, state)
