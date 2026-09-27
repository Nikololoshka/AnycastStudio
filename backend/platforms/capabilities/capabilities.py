from dataclasses import dataclass, field
from typing import Literal

Scheduling = Literal["native", "stagedPublish", "deferredUpload", "unsupported"]


@dataclass(frozen=True)
class Capabilities:
    label: str
    scheduling: Scheduling
    title: bool
    description: bool
    hashtags: bool
    drafts: bool
    max_file_size: int | None = None
    supported_mime_types: tuple[str, ...] = field(default_factory=tuple)

    def as_json(self) -> dict:
        return {
            "label": self.label,
            "scheduling": self.scheduling,
            "title": self.title,
            "description": self.description,
            "hashtags": self.hashtags,
            "drafts": self.drafts,
            "maxFileSize": self.max_file_size,
            "supportedMimeTypes": list(self.supported_mime_types),
        }
