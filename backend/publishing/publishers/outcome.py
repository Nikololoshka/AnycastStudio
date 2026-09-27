import time
from dataclasses import dataclass

from ..models import PublicationTarget


@dataclass(frozen=True)
class Published:
    status: str
    url: str = ""
    resume_state: dict | None = None


def awaiting_confirmation(**state) -> Published:
    return Published(
        PublicationTarget.Status.PROCESSING,
        resume_state={"confirming_since": time.time(), "polls": 0, **state},
    )
