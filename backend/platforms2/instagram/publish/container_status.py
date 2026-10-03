from typing import ClassVar

from platforms2.core import PlatformError, PlatformFailure

from ..instagram_answer import InstagramAnswer


class ContainerStatus(InstagramAnswer):
    FINISHED: ClassVar = "FINISHED"
    PUBLISHED: ClassVar = "PUBLISHED"
    ERROR: ClassVar = "ERROR"
    EXPIRED: ClassVar = "EXPIRED"
    DETAILS_LIMIT: ClassVar = 500

    status_code: str = ""
    status: str = ""

    @property
    def is_ready(self) -> bool:
        return self.status_code == self.FINISHED

    @property
    def is_published(self) -> bool:
        return self.status_code == self.PUBLISHED

    @property
    def is_dead(self) -> bool:
        return self.status_code in (self.ERROR, self.EXPIRED)

    def failure(self) -> PlatformError:
        if self.status_code == self.EXPIRED:
            message = "The Instagram upload expired before it was published"
            return PlatformError(PlatformFailure.REFUSED, message, details=self.EXPIRED)
        details = self.status[: self.DETAILS_LIMIT] or self.ERROR
        return PlatformError(PlatformFailure.FILE_REJECTED, "Instagram could not process the video", details=details)
