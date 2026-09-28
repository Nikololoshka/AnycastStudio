import logging

from ...core.config import UploadConfig
from ...core.ports import Clock
from ...core.upload import UploadDriver
from .post_info import PostInfo
from .protocol import DirectPostProtocol
from .session import TikTokUploadSession
from .state import ChunkPlan, ResumeState

UPLOAD_URL_LIFETIME_SECONDS = 55 * 60

logger = logging.getLogger(__name__)


class TikTokUploader:
    def __init__(self, protocol: DirectPostProtocol, config: UploadConfig, clock: Clock):
        self._protocol = protocol
        self._config = config
        self._clock = clock

    def upload(
        self,
        *,
        path,
        size: int,
        mime_type: str,
        post_info: PostInfo,
        access_token: str,
        resume: ResumeState | None = None,
        on_progress=None,
        should_cancel=None,
    ) -> str:
        state = self._resumed(resume) or self._start(access_token, post_info, size)
        session = TikTokUploadSession(self._protocol, state, size, mime_type)
        return UploadDriver(on_progress, should_cancel).drive(session, path=path, size=size)

    def _resumed(self, resume: ResumeState | None) -> ResumeState | None:
        if resume is None:
            return None
        if resume.expired(self._now()):
            logger.info("TikTok upload %s outlived its upload URL, starting again", resume.publish_id)
            return None
        return resume

    def _start(self, access_token: str, post_info: PostInfo, size: int) -> ResumeState:
        plan = ChunkPlan.of(size, self._config.chunk_bytes)
        opened = self._protocol.init(access_token, post_info, size, plan)
        return ResumeState(
            publish_id=opened.publish_id,
            upload_url=opened.upload_url,
            chunk_size=plan.chunk_size,
            total_chunks=plan.total_chunks,
            expires_at=self._now() + UPLOAD_URL_LIFETIME_SECONDS,
        )

    def _now(self) -> float:
        return self._clock.now().timestamp()
