from typing import ClassVar

from platforms.core import PlatformError, PlatformFailure

from ...core import XAnswer


class ProcessingError(XAnswer):
    message: str = ""
    name: str = ""


class ProcessingInfo(XAnswer):
    SUCCEEDED: ClassVar = "succeeded"
    FAILED: ClassVar = "failed"
    DETAILS_LIMIT: ClassVar = 500

    state: str = "succeeded"
    error: ProcessingError = ProcessingError()

    @property
    def is_ready(self) -> bool:
        return self.state == self.SUCCEEDED

    @property
    def is_failed(self) -> bool:
        return self.state == self.FAILED

    def failure(self) -> PlatformError:
        message = (self.error.message or self.error.name)[: self.DETAILS_LIMIT] or "X could not process the video"
        return PlatformError(PlatformFailure.FILE_REJECTED, message, details=self.FAILED)


class Media(XAnswer):
    processing_info: ProcessingInfo = ProcessingInfo()


class MediaStatus(XAnswer):
    data: Media = Media()
