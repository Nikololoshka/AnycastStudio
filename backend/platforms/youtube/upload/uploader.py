from dataclasses import replace

from ...core.config import UploadConfig
from ...core.upload import UploadDriver
from .metadata import VideoMetadata
from .protocol import ResumableProtocol
from .session import YouTubeUploadSession
from .state import ResumeState


class YouTubeUploader:
    def __init__(self, protocol: ResumableProtocol, config: UploadConfig):
        self._protocol = protocol
        self._config = config

    def upload(
        self,
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
        session = self._session(access_token, metadata, size, mime_type, resume)
        return UploadDriver(on_progress, should_cancel).drive(session, path=path, size=size)

    def _session(
        self, access_token: str, metadata: VideoMetadata, size: int, mime_type: str, resume: ResumeState | None
    ) -> YouTubeUploadSession:
        if resume is None:
            state = ResumeState(session_uri=self._protocol.open(access_token, metadata, size, mime_type))
            return YouTubeUploadSession(self._protocol, self._config, state, size, mime_type)

        progress = self._protocol.ask_progress(resume, size)
        if self._protocol.is_complete(progress):
            video_id = self._protocol.video_id_of(progress, size)
            return YouTubeUploadSession(self._protocol, self._config, resume, size, mime_type, video_id=video_id)
        state = replace(resume, offset=self._protocol.persisted_offset(progress))
        return YouTubeUploadSession(self._protocol, self._config, state, size, mime_type)
