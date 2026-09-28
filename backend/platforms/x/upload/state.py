from dataclasses import dataclass

from ...core.upload import ResumableState

MEDIA_LIFETIME_SECONDS = 23 * 60 * 60


@dataclass(frozen=True)
class ResumeState(ResumableState):
    media_id: str
    segment_bytes: int
    next_segment: int = 0
    created_at: float = 0

    def expired(self, now: float) -> bool:
        return now - self.created_at >= MEDIA_LIFETIME_SECONDS

    def uploaded_bytes(self, size: int) -> int:
        return min(self.next_segment * self.segment_bytes, size)

    def segment_count(self, size: int) -> int:
        return -(-size // self.segment_bytes)
