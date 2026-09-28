import logging
import re

from ...core.errors import FailureType, PlatformError
from ...core.upload import TokenRejectionGuard
from ..client import YouTubeClient
from .metadata import VideoMetadata
from .responses import UploadedVideo
from .state import ResumeState

UPLOAD_ENDPOINT = "https://www.googleapis.com/upload/youtube/v3/videos"

RANGE_PATTERN = re.compile(r"bytes=0-(\d+)")

logger = logging.getLogger(__name__)


class ResumableProtocol:
    def __init__(self, client: YouTubeClient):
        self._client = client

    def open(self, access_token: str, metadata: VideoMetadata, size: int, mime_type: str) -> str:
        params = {
            "uploadType": "resumable",
            "part": "snippet,status",
            "notifySubscribers": str(metadata.notify_subscribers).lower(),
        }
        headers = {
            **self._client.bearer(access_token),
            "X-Upload-Content-Type": mime_type,
            "X-Upload-Content-Length": str(size),
        }
        response = self._client.send("POST", UPLOAD_ENDPOINT, params=params, headers=headers, json=metadata.as_body())

        location = response.headers.get("Location")
        if not location:
            raise PlatformError(FailureType.PLATFORM, "YouTube did not open an upload session")
        return location

    def ask_progress(self, state: ResumeState, size: int):
        return self._put(state, {"Content-Range": f"bytes */{size}"})

    def send_piece(self, state: ResumeState, piece: bytes, size: int, mime_type: str):
        last = state.offset + len(piece) - 1
        headers = {"Content-Range": f"bytes {state.offset}-{last}/{size}", "Content-Type": mime_type}
        return self._put(state, headers, piece)

    def video_id_of(self, response, size: int) -> str:
        refusal = "YouTube accepted the file but returned no video id"
        video = self._client.parse(response, UploadedVideo, refusal=refusal)
        logger.info("Uploaded %d bytes to YouTube as %s", size, video.id)
        return video.id

    @staticmethod
    def is_complete(response) -> bool:
        return response.status_code in (200, 201)

    @staticmethod
    def persisted_offset(response) -> int:
        match = RANGE_PATTERN.search(response.headers.get("Range", ""))
        return int(match.group(1)) + 1 if match else 0

    def _put(self, state: ResumeState, headers: dict, body: bytes = b""):
        guard = TokenRejectionGuard(state)
        return guard.run(lambda: self._client.send("PUT", state.session_uri, headers=headers, data=body))
