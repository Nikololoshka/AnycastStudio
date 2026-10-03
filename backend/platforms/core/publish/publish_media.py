from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PublishMedia:
    path: Path
    size_bytes: int
    mime_type: str
    duration_seconds: float | None = None
