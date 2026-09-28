from abc import ABC, abstractmethod

from .state import ResumableState
from .video_file import VideoFile


class UploadSession(ABC):
    state: ResumableState

    @property
    @abstractmethod
    def done(self) -> bool: ...

    @property
    @abstractmethod
    def uploaded(self) -> int: ...

    @abstractmethod
    def send_next(self, video: VideoFile) -> None: ...

    @abstractmethod
    def finish(self) -> str: ...
