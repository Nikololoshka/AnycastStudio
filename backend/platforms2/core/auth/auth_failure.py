from enum import StrEnum


class AuthFailure(StrEnum):
    NETWORK = "network"
    RATE_LIMITED = "rate_limited"
    TOKEN_REJECTED = "token_rejected"
    GRANT_REVOKED = "grant_revoked"
    SCOPE_MISSING = "scope_missing"
    MISCONFIGURED = "misconfigured"
    REFUSED = "refused"
    UNEXPECTED = "unexpected"

    @property
    def transient(self) -> bool:
        return self in (AuthFailure.NETWORK, AuthFailure.RATE_LIMITED)
