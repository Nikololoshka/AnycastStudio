from dataclasses import dataclass

from ...core.upload import ResumableState

CONTAINER_LIFETIME_SECONDS = 23 * 60 * 60


@dataclass
class ResumeState(ResumableState):
    container_id: str
    offset: int = 0
    created_at: float = 0

    def expired(self, now: float) -> bool:
        return now - self.created_at >= CONTAINER_LIFETIME_SECONDS
