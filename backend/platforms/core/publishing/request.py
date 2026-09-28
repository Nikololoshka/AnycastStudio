from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class NewTarget:
    platform: str
    account_id: int
    settings: Mapping = field(default_factory=dict)


@dataclass(frozen=True)
class NewPublication:
    owner_id: int
    asset_id: int
    title: str
    description: str
    hashtags: tuple[str, ...]
    publish_at: datetime | None
    targets: tuple[NewTarget, ...]


@dataclass(frozen=True)
class CreatedTarget:
    id: int
    platform: str


@dataclass(frozen=True)
class CreatedPublication:
    id: int
    publish_at: datetime | None
    targets: tuple[CreatedTarget, ...]
