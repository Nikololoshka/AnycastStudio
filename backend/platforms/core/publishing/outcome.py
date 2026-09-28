import time
from dataclasses import dataclass

from .status import TargetStatus


@dataclass(frozen=True)
class Published:
    status: TargetStatus
    url: str = ""
    resume_state: dict | None = None

    @classmethod
    def awaiting_confirmation(cls, **state) -> "Published":
        return cls(TargetStatus.PROCESSING, resume_state={"confirming_since": time.time(), "polls": 0, **state})


@dataclass(frozen=True)
class NotReady:
    pass


@dataclass(frozen=True)
class ReadyToCommit:
    pass


Confirmation = Published | NotReady | ReadyToCommit
