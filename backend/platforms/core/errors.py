from enum import StrEnum


class FailureType(StrEnum):
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    RATE_LIMIT = "rate_limit"
    PLATFORM = "platform"
    VALIDATION = "validation"
    FILE = "file"
    UNKNOWN = "unknown"


class PlatformError(Exception):
    def __init__(self, type: FailureType, message: str, details: str = "", retryable: bool = False):
        super().__init__(message)
        self.type = FailureType(type)
        self.message = message
        self.details = details
        self.retryable = retryable

    def __str__(self) -> str:
        return self.message

    def as_failure(self) -> dict:
        return {"type": self.type.value, "message": self.message, "details": self.details}


class ProviderError(PlatformError):
    def __init__(self, message: str, transient: bool = False):
        kind = FailureType.NETWORK if transient else FailureType.AUTHENTICATION
        super().__init__(kind, message, retryable=transient)

    @property
    def transient(self) -> bool:
        return self.retryable


class NeedsFreshToken(PlatformError):
    def __init__(self, state: dict | None, message: str):
        super().__init__(FailureType.AUTHENTICATION, message)
        self.state = state


class UploadCancelled(PlatformError):
    def __init__(self, state: dict):
        super().__init__(FailureType.UNKNOWN, "cancelled")
        self.state = state


class MediaMissing(PlatformError):
    def __init__(self):
        super().__init__(FailureType.FILE, "The uploaded video is no longer on the server")


class MaybePublished(PlatformError):
    def __init__(self, label: str, details: str = ""):
        super().__init__(
            FailureType.PLATFORM,
            f"The post may have been created; check {label} before publishing again",
            details=details,
        )


class DomainError(Exception):
    def __init__(self, **fields):
        super().__init__(fields.get("message", self.__class__.__name__))
        self.fields = fields


class NotFound(DomainError):
    def __init__(self, message: str = ""):
        super().__init__(**({"message": message} if message else {}))


class Invalid(DomainError):
    def __init__(self, field: str, message: str):
        super().__init__(errors=[{"field": field, "message": message}])


class Conflict(DomainError):
    def __init__(self, message: str, **fields):
        super().__init__(message=message, **fields)


class LimitReached(DomainError):
    def __init__(self, message: str, limit: int):
        super().__init__(message=message, limit=limit)


class AccountNeedsReauth(DomainError):
    def __init__(self, platform: str):
        super().__init__(message="account_needs_reauth", platform=platform)
