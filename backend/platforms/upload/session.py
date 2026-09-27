from typing import Protocol

from ..http import FILE, PlatformFailure
from .errors import UploadCancelled
from .state import ResumableState


class UploadSession(Protocol):
    state: ResumableState

    @property
    def done(self) -> bool: ...

    @property
    def uploaded(self) -> int: ...

    def send_next(self, handle) -> None: ...

    def finish(self) -> str: ...


def read_piece(handle, offset: int, length: int) -> bytes:
    handle.seek(offset)
    piece = handle.read(length) if length > 0 else b""
    if not piece or len(piece) != length:
        raise PlatformFailure(FILE, "The video is shorter than it claimed to be")
    return piece


def drive(session: UploadSession, *, path, size: int, on_progress=None, should_cancel=None) -> str:
    with open(path, "rb") as handle:
        while not session.done:
            if should_cancel and should_cancel():
                raise UploadCancelled(session.state.as_dict())

            session.send_next(handle)
            if on_progress:
                on_progress(session.uploaded, size, session.state.as_dict())

    return session.finish()
