from ..errors import UploadCancelled
from .session import UploadSession
from .video_file import VideoFile


class UploadDriver:
    def __init__(self, on_progress=None, should_cancel=None):
        self._on_progress = on_progress
        self._should_cancel = should_cancel

    def drive(self, session: UploadSession, *, path, size: int) -> str:
        with open(path, "rb") as handle:
            video = VideoFile(handle)
            while not session.done:
                if self._should_cancel and self._should_cancel():
                    raise UploadCancelled(session.state.as_dict())

                session.send_next(video)
                if self._on_progress:
                    self._on_progress(session.uploaded, size, session.state.as_dict())

        return session.finish()
