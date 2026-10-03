from dataclasses import dataclass
from typing import Self


@dataclass(frozen=True)
class ChunkPlan:
    size: int
    chunk_size: int
    total_chunks: int

    @classmethod
    def of(cls, size: int, preferred: int) -> Self:
        chunk_size = max(1, min(size, preferred))
        return cls(size, chunk_size, max(1, size // chunk_size))

    def bounds_of(self, index: int) -> tuple[int, int]:
        first = index * self.chunk_size
        last = self.size - 1 if index == self.total_chunks - 1 else first + self.chunk_size - 1
        return first, last

    def as_source_info(self) -> dict:
        return {
            "source": "FILE_UPLOAD",
            "video_size": self.size,
            "chunk_size": self.chunk_size,
            "total_chunk_count": self.total_chunks,
        }
