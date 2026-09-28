import logging
from dataclasses import replace

from ...core.upload import UploadSession, VideoFile
from .protocol import MediaUploadProtocol
from .state import ResumeState

logger = logging.getLogger(__name__)


class XUploadSession(UploadSession):
    def __init__(self, protocol: MediaUploadProtocol, state: ResumeState, size: int, access_token: str):
        self.state = state
        self._protocol = protocol
        self._size = size
        self._access_token = access_token

    @property
    def done(self) -> bool:
        return self.state.next_segment >= self.state.segment_count(self._size)

    @property
    def uploaded(self) -> int:
        return self.state.uploaded_bytes(self._size)

    def send_next(self, video: VideoFile) -> None:
        offset = self.state.next_segment * self.state.segment_bytes
        piece = video.piece(offset, min(self.state.segment_bytes, self._size - offset))
        self._protocol.append(self._access_token, self.state, piece)
        self.state = replace(self.state, next_segment=self.state.next_segment + 1)

    def finish(self) -> str:
        self._protocol.finalize(self._access_token, self.state)
        logger.info("Uploaded %d bytes to X as media %s", self._size, self.state.media_id)
        return self.state.media_id
