from dataclasses import dataclass
from datetime import datetime

from .new_target import NewTarget


@dataclass(frozen=True)
class NewPublication:
    owner_id: int
    asset_id: int
    title: str
    description: str
    hashtags: tuple[str, ...]
    publish_at: datetime | None
    targets: tuple[NewTarget, ...]
