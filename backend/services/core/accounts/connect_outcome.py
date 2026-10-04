from enum import StrEnum


class ConnectOutcome(StrEnum):
    CONNECTED = "connected"
    INVALID = "invalid"
    CANCELLED = "cancelled"
    FAILED = "failed"
