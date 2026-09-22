"""Uploading a video to YouTube, resumably.

A port of the Rust command the desktop client used, with one addition that only
matters on a server: the session URI and the confirmed offset are handed back
after every chunk, so a worker that dies mid-upload resumes instead of sending
gigabytes again.

Google's protocol: open a session and keep the Location header, then PUT
pieces with a Content-Range. A 308 means "still going" and the Range header of
that reply — not the client's arithmetic — says how much actually landed.
"""

import logging
import re
from dataclasses import dataclass

from django.conf import settings

from ..base import ProviderError
from ..http import AUTHENTICATION, PlatformFailure, json_dict, request, with_retry

UPLOAD_ENDPOINT = "https://www.googleapis.com/upload/youtube/v3/videos"
LABEL = "YouTube"

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
    """Open a resumable session and return the URI to send the bytes to."""
    params = {
        "uploadType": "resumable",
        "part": "snippet,status",
        "notifySubscribers": str(metadata.notify_subscribers).lower(),
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": mime_type,
        "X-Upload-Content-Length": str(size),
    }

    response = with_retry(
        lambda: request(
            "POST",
            UPLOAD_ENDPOINT,
            label=LABEL,
            params=params,
            headers=headers,
            json=metadata.as_body(),
        ),
        label=LABEL,
    )

    location = response.headers.get("Location")
    if not location:
        raise PlatformFailure("platform", "YouTube did not open an upload session")
    return location


def confirmed_offset(response, fallback: int) -> int:
    """How far Google says it got. Its answer wins over ours."""
    header = response.headers.get("Range", "")
    match = RANGE_PATTERN.search(header)
    return int(match.group(1)) + 1 if match else fallback


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
    """Send the file and return the video id.

    `on_progress(uploaded, total, state)` is called after every chunk with the
    resume point, so the caller can persist it. `should_cancel()` is checked
    between chunks, which is where the desktop client checked its flag too.
    """
    state = resume or ResumeState(
        session_uri=start_session(access_token, metadata, size, mime_type)
    )

    chunk_size = settings.PLATFORM_CHUNK_BYTES

    with open(path, "rb") as handle:
        while state.offset < size:
            if should_cancel and should_cancel():
                raise Cancelled(state)

            handle.seek(state.offset)
            piece = handle.read(chunk_size)
            if not piece:
                raise PlatformFailure("file", "The video is shorter than it claimed to be")

            last = state.offset + len(piece) - 1
            headers = {
                "Content-Range": f"bytes {state.offset}-{last}/{size}",
                "Content-Type": mime_type,
            }

            try:
                response = with_retry(
                    lambda body=piece, sent=headers: request(
                        "PUT", state.session_uri, label=LABEL, headers=sent, data=body
                    ),
                    label=LABEL,
                )
            except PlatformFailure as failure:
                # The token died mid-upload. Hand the resume point out so the
                # caller can refresh and carry on from here.
                if failure.type == AUTHENTICATION:
                    raise NeedsFreshToken(state, failure.message) from None
                raise

            state.offset = confirmed_offset(response, state.offset + len(piece))
            if on_progress:
                on_progress(state.offset, size, state)

            if response.status_code in (200, 201):
                break

    body = json_dict(response)
    video_id = body.get("id")
    if not video_id:
        raise PlatformFailure("platform", "YouTube accepted the file but returned no video id")

    logger.info("Uploaded %d bytes to YouTube as %s", size, video_id)
    return str(video_id)


class Cancelled(Exception):
    def __init__(self, state: ResumeState):
        super().__init__("cancelled")
        self.state = state


class NeedsFreshToken(Exception):
    """The access token expired mid-upload; everything sent so far is still there."""

    def __init__(self, state: ResumeState, message: str):
        super().__init__(message)
        self.state = state


__all__ = [
    "Cancelled",
    "NeedsFreshToken",
    "ProviderError",
    "ResumeState",
    "VideoMetadata",
    "confirmed_offset",
    "start_session",
    "upload",
]
