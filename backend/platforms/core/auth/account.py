from dataclasses import dataclass
from enum import StrEnum


class AccountStatus(StrEnum):
    ACTIVE = "active"
    NEEDS_REAUTH = "needs_reauth"
    REVOKED = "revoked"


@dataclass(frozen=True)
class AccountRecord:
    id: int
    platform: str
    status: AccountStatus
