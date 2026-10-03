from .platform_failure import PlatformFailure


class PlatformError(Exception):
    def __init__(self, failure: PlatformFailure, message: str, details: str = ""):
        super().__init__(message)
        self.failure = failure
        self.message = message
        self.details = details

    @property
    def transient(self) -> bool:
        return self.failure.transient
