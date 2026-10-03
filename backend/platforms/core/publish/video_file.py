import asyncio
from pathlib import Path

from ..platform_error import PlatformError
from ..platform_failure import PlatformFailure


class VideoFile:
    def __init__(self, path: Path):
        self._path = path

    async def piece(self, offset: int, length: int) -> bytes:
        try:
            piece = await asyncio.to_thread(self._read, offset, length)
        except FileNotFoundError:
            message = "The uploaded video is no longer on the server"
            raise PlatformError(PlatformFailure.MEDIA_MISSING, message) from None
        if len(piece) != length:
            raise PlatformError(PlatformFailure.MEDIA_MISSING, "The video is shorter than it claimed to be")
        return piece

    def _read(self, offset: int, length: int) -> bytes:
        with open(self._path, "rb") as handle:
            handle.seek(offset)
            return handle.read(length)
