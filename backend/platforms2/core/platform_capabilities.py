from dataclasses import dataclass

from .scheduling import Scheduling


@dataclass(frozen=True)
class PlatformCapabilities:
    label: str
    scheduling: Scheduling
    title: bool
    description: bool
    hashtags: bool
    drafts: bool
    max_file_size: int | None = None
    supported_mime_types: tuple[str, ...] = ()

    @property
    def defers_upload(self) -> bool:
        return self.scheduling == Scheduling.DEFERRED_UPLOAD

    def supports(self, mime_type: str) -> bool:
        return not mime_type or mime_type in self.supported_mime_types

    def fits(self, size_bytes: int) -> bool:
        return self.max_file_size is None or size_bytes <= self.max_file_size

    def as_json(self) -> dict:
        return {
            "label": self.label,
            "scheduling": self.scheduling.value,
            "title": self.title,
            "description": self.description,
            "hashtags": self.hashtags,
            "drafts": self.drafts,
            "maxFileSize": self.max_file_size,
            "supportedMimeTypes": list(self.supported_mime_types),
        }
