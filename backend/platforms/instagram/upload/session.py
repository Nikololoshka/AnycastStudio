import logging
from dataclasses import replace

from ...core.config import UploadConfig
from ...core.upload import UploadSession, VideoFile
from .protocol import ContainerUploadProtocol
from .state import ResumeState

logger = logging.getLogger(__name__)


class InstagramUploadSession(UploadSession):
    def __init__(
        self, protocol: ContainerUploadProtocol, config: UploadConfig, state: ResumeState, size: int, access_token: str
    ):
        self.state = state
        self._protocol = protocol
        self._config = config
        self._size = size
        self._access_token = access_token

    @property
    def done(self) -> bool:
        return self.state.offset >= self._size

    @property
    def uploaded(self) -> int:
        return self.state.offset

    def send_next(self, video: VideoFile) -> None:
        length = min(self._config.chunk_bytes, self._size - self.state.offset)
        piece = video.piece(self.state.offset, length)
        self._protocol.send_piece(self._access_token, self.state, piece, self._size)
        self.state = replace(self.state, offset=self.state.offset + length)

    def finish(self) -> str:
        logger.info("Uploaded %d bytes to Instagram as container %s", self._size, self.state.container_id)
        return self.state.container_id
