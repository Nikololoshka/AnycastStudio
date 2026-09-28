from dataclasses import replace

from ...core.config import UploadConfig
from ...core.errors import FailureType, PlatformError
from ...core.upload import UploadSession, VideoFile
from .protocol import ResumableProtocol
from .state import ResumeState


class YouTubeUploadSession(UploadSession):
    def __init__(
        self,
        protocol: ResumableProtocol,
        config: UploadConfig,
        state: ResumeState,
        size: int,
        mime_type: str,
        video_id: str | None = None,
    ):
        self.state = state
        self._protocol = protocol
        self._config = config
        self._size = size
        self._mime_type = mime_type
        self._video_id = video_id
        self._chunks_without_progress = 0

    @property
    def done(self) -> bool:
        return self._video_id is not None

    @property
    def uploaded(self) -> int:
        return self.state.offset

    def send_next(self, video: VideoFile) -> None:
        length = min(self._config.chunk_bytes, self._size - self.state.offset)
        piece = video.piece(self.state.offset, length)
        response = self._protocol.send_piece(self.state, piece, self._size, self._mime_type)
        if self._protocol.is_complete(response):
            self.state = replace(self.state, offset=self._size)
            self._video_id = self._protocol.video_id_of(response, self._size)
            return

        previous = self.state.offset
        self.state = replace(self.state, offset=self._protocol.persisted_offset(response))
        self._chunks_without_progress = self._chunks_without_progress + 1 if self.state.offset <= previous else 0
        if self._chunks_without_progress >= self._config.stall_limit:
            raise PlatformError(FailureType.PLATFORM, "YouTube stopped accepting the upload")

    def finish(self) -> str:
        return self._video_id or ""
