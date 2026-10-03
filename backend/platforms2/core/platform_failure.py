from enum import StrEnum


class PlatformFailure(StrEnum):
    NETWORK = "network"
    RATE_LIMITED = "rate_limited"
    TOKEN_REJECTED = "token_rejected"
    GRANT_REVOKED = "grant_revoked"
    SCOPE_MISSING = "scope_missing"
    MISCONFIGURED = "misconfigured"
    INVALID = "invalid"
    FILE_REJECTED = "file_rejected"
    MEDIA_MISSING = "media_missing"
    REFUSED = "refused"
    UNCONFIRMED = "unconfirmed"
    UNEXPECTED = "unexpected"

    @property
    def transient(self) -> bool:
        return self in (PlatformFailure.NETWORK, PlatformFailure.RATE_LIMITED)
