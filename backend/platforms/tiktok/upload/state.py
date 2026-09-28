from dataclasses import dataclass

from ...core.upload import ResumableState


@dataclass(frozen=True)
class ChunkPlan:
    chunk_size: int
    total_chunks: int

    @classmethod
    def of(cls, size: int, preferred: int) -> "ChunkPlan":
        chunk_size = max(1, min(size, preferred))
        return cls(chunk_size, max(1, size // chunk_size))


@dataclass
class ResumeState(ResumableState):
    publish_id: str
    upload_url: str
    chunk_size: int
    total_chunks: int
    next_chunk: int = 0
    expires_at: float = 0

    def expired(self, now: float) -> bool:
        return now >= self.expires_at

    def uploaded_bytes(self, size: int) -> int:
        return min(self.next_chunk * self.chunk_size, size)

    def bounds_of(self, index: int, size: int) -> tuple[int, int]:
        start = index * self.chunk_size
        end = size - 1 if index == self.total_chunks - 1 else start + self.chunk_size - 1
        return start, end
