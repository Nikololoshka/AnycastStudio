from ..errors import FailureType, MediaMissing, PlatformError


class FailureMapper:
    def failure_of(self, exception: Exception) -> dict:
        if isinstance(exception, PlatformError):
            return exception.as_failure()
        if isinstance(exception, FileNotFoundError):
            return MediaMissing().as_failure()
        return {"type": FailureType.UNKNOWN.value, "message": str(exception) or exception.__class__.__name__}
