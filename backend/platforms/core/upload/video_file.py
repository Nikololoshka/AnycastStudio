from ..errors import FailureType, PlatformError


class VideoFile:
    def __init__(self, handle):
        self._handle = handle

    def piece(self, offset: int, length: int) -> bytes:
        self._handle.seek(offset)
        piece = self._handle.read(length) if length > 0 else b""
        if not piece or len(piece) != length:
            raise PlatformError(FailureType.FILE, "The video is shorter than it claimed to be")
        return piece
