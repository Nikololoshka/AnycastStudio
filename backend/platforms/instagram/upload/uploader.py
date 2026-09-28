import logging
from dataclasses import replace

from ...core.config import UploadConfig
from ...core.errors import FailureType, PlatformError
from ...core.ports import Clock
from ...core.upload import UploadDriver
from ..publish.status import ContainerApi
from .protocol import ContainerUploadProtocol
from .reel import ReelInfo
from .session import InstagramUploadSession
from .state import ResumeState

logger = logging.getLogger(__name__)


class InstagramUploader:
    def __init__(self, protocol: ContainerUploadProtocol, containers: ContainerApi, config: UploadConfig, clock: Clock):
        self._protocol = protocol
        self._containers = containers
        self._config = config
        self._clock = clock

    def upload(
        self,
        *,
        path,
        size: int,
        ig_user_id: str,
        reel: ReelInfo,
        access_token: str,
        resume: ResumeState | None = None,
        on_progress=None,
        should_cancel=None,
    ) -> str:
        if size <= 0:
            raise PlatformError(FailureType.VALIDATION, "The video is empty")

        state = self._resumed(access_token, resume, size) or self._start(access_token, ig_user_id, reel)
        session = InstagramUploadSession(self._protocol, self._config, state, size, access_token)
        return UploadDriver(on_progress, should_cancel).drive(session, path=path, size=size)

    def _start(self, access_token: str, ig_user_id: str, reel: ReelInfo) -> ResumeState:
        container_id = self._protocol.create(access_token, ig_user_id, reel)
        return ResumeState(container_id=container_id, created_at=self._now())

    def _resumed(self, access_token: str, resume: ResumeState | None, size: int) -> ResumeState | None:
        if resume is None:
            return None
        if resume.expired(self._now()):
            logger.info("Instagram container %s is too old to finish, starting again", resume.container_id)
            return None

        status = self._containers.status(access_token, resume.container_id, resume)
        if status.is_dead or status.is_published:
            logger.info("Instagram container %s is %s, starting again", resume.container_id, status.status_code)
            return None
        if status.bytes_transferred is not None:
            return replace(resume, offset=min(status.bytes_transferred, size))
        return resume

    def _now(self) -> float:
        return self._clock.now().timestamp()
