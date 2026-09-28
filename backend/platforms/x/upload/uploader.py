import logging
from dataclasses import replace

from ...core.config import UploadConfig
from ...core.errors import FailureType, PlatformError
from ...core.ports import Clock
from ...core.upload import UploadDriver
from .protocol import MediaUploadProtocol
from .session import XUploadSession
from .state import ResumeState

MAX_SEGMENT_BYTES = 4 * 1024**2

logger = logging.getLogger(__name__)


class XUploader:
    def __init__(self, protocol: MediaUploadProtocol, config: UploadConfig, clock: Clock):
        self._protocol = protocol
        self._config = config
        self._clock = clock

    def upload(
        self,
        *,
        path,
        size: int,
        mime_type: str,
        access_token: str,
        resume: ResumeState | None = None,
        on_progress=None,
        should_cancel=None,
    ) -> str:
        if size <= 0:
            raise PlatformError(FailureType.VALIDATION, "The video is empty")

        state = self._resumed(resume, size) or self._start(access_token, size, mime_type)
        session = XUploadSession(self._protocol, state, size, access_token)
        return UploadDriver(on_progress, should_cancel).drive(session, path=path, size=size)

    @property
    def segment_bytes(self) -> int:
        return min(self._config.chunk_bytes, MAX_SEGMENT_BYTES)

    def _start(self, access_token: str, size: int, mime_type: str) -> ResumeState:
        media_id = self._protocol.initialize(access_token, size, mime_type)
        return ResumeState(media_id=media_id, segment_bytes=self.segment_bytes, created_at=self._now())

    def _resumed(self, resume: ResumeState | None, size: int) -> ResumeState | None:
        if resume is None:
            return None
        if resume.expired(self._now()):
            logger.info("X media %s is too old to finish, starting again", resume.media_id)
            return None
        return replace(resume, next_segment=min(resume.next_segment, resume.segment_count(size)))

    def _now(self) -> float:
        return self._clock.now().timestamp()
