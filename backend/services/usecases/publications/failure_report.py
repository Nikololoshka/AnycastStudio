from platforms.core import PlatformError, PlatformFailure


class FailureReport:
    MEDIA_MISSING = "The uploaded video is no longer on the server"

    @classmethod
    def of(cls, exception: Exception) -> dict:
        if isinstance(exception, PlatformError):
            return exception.as_failure()
        if isinstance(exception, FileNotFoundError):
            return PlatformError(PlatformFailure.MEDIA_MISSING, cls.MEDIA_MISSING).as_failure()
        return PlatformError(PlatformFailure.UNEXPECTED, type(exception).__name__).as_failure()
