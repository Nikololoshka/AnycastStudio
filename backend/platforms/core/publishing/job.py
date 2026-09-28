from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class MediaInfo:
    size_bytes: int
    mime_type: str
    duration_seconds: float | None = None


@dataclass(frozen=True)
class PublicationDraft:
    title: str
    description: str
    hashtags: tuple[str, ...]
    media: MediaInfo
    settings: Mapping = field(default_factory=dict)

    def caption(self) -> str:
        tags = " ".join(f"#{tag}" for tag in self.hashtags)
        return "\n\n".join(part for part in (self.title.strip(), self.description.strip(), tags) if part)


@dataclass(frozen=True)
class PublishJob:
    target_id: int
    platform: str
    account_id: int
    external_id: str
    draft: PublicationDraft
    video_path: Path
    publish_at: datetime | None = None
    uploaded_media_id: str = ""
    resume_state: dict | None = None

    def resumed_from(self, state: dict | None) -> "PublishJob":
        return replace(self, resume_state=state)
