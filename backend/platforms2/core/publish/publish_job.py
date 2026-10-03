from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from .publish_draft import PublishDraft
from .publish_media import PublishMedia


@dataclass(frozen=True)
class PublishJob:
    target_id: int
    account_id: int
    external_id: str
    draft: PublishDraft
    media: PublishMedia
    publish_at: datetime | None = None
    media_id: str = ""
    confirmation_state: Mapping = field(default_factory=dict)
