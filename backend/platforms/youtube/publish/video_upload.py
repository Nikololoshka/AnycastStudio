from typing import override

from googleapiclient.http import MediaUpload

from platforms.core import PublishMedia


class VideoUpload(MediaUpload):

    def __init__(self, media: PublishMedia, chunk_bytes: int):
        self._media = media
        self._chunk_bytes = chunk_bytes

    @override
    def chunksize(self) -> int:
        return self._chunk_bytes

    @override
    def mimetype(self) -> str:
        return self._media.mime_type

    @override
    def size(self) -> int:
        return self._media.size_bytes

    @override
    def resumable(self) -> bool:
        return True

    @override
    def getbytes(self, begin: int, length: int) -> bytes:
        with open(self._media.path, "rb") as handle:
            handle.seek(begin)
            return handle.read(length)
