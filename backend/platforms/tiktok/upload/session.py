import logging
from dataclasses import replace

from ...core.upload import UploadSession, VideoFile
from .protocol import DirectPostProtocol
from .state import ResumeState

logger = logging.getLogger(__name__)


class TikTokUploadSession(UploadSession):
    def __init__(self, protocol: DirectPostProtocol, state: ResumeState, size: int, mime_type: str):
        self.state = state
        self._protocol = protocol
        self._size = size
        self._mime_type = mime_type

    @property
    def done(self) -> bool:
        return self.state.next_chunk >= self.state.total_chunks

    @property
    def uploaded(self) -> int:
        return self.state.uploaded_bytes(self._size)

    def send_next(self, video: VideoFile) -> None:
        first, last = self.state.bounds_of(self.state.next_chunk, self._size)
        piece = video.piece(first, last - first + 1)
        is_last = self.state.next_chunk == self.state.total_chunks - 1
        self._protocol.send_chunk(self.state.upload_url, piece, first, last, self._size, self._mime_type, is_last)
        self.state = replace(self.state, next_chunk=self.state.next_chunk + 1)

    def finish(self) -> str:
        logger.info("Uploaded %d bytes to TikTok as %s", self._size, self.state.publish_id)
        return self.state.publish_id
