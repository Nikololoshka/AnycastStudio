from dataclasses import dataclass, field
from enum import StrEnum


class OAuthSessionStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


class ConnectOutcome(StrEnum):
    CONNECTED = "connected"
    INVALID = "invalid"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True)
class OAuthSessionRecord:
    id: int
    owner_id: int
    platform: str
    code_verifier: str = field(default="", repr=False)
