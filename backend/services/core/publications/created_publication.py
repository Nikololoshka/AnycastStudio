from dataclasses import dataclass
from datetime import datetime

from .created_target import CreatedTarget


@dataclass(frozen=True)
class CreatedPublication:
    id: int
    publish_at: datetime | None
    targets: tuple[CreatedTarget, ...]
