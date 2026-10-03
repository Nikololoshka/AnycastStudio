from dataclasses import dataclass
from typing import Self

from platforms.core import PublishJob

from .youtube_options import YouTubeOptions


@dataclass(frozen=True)
class VideoMetadata:
    title: str
    description: str
    tags: tuple[str, ...]
    privacy_status: str
    options: YouTubeOptions

    @classmethod
    def of(cls, job: PublishJob, options: YouTubeOptions) -> Self:
        draft = job.draft
        return cls(
            title=draft.title,
            description=options.description_with(draft.description, draft.hashtags),
            tags=draft.hashtags,
            privacy_status="private" if job.publish_at else options.privacy_status,
            options=options,
        )

    def as_body(self) -> dict:
        return {
            "snippet": {
                "title": self.title,
                "description": self.description,
                "tags": list(self.tags),
                "categoryId": self.options.category_id,
            },
            "status": {"privacyStatus": self.privacy_status, **self.options.status_fields()},
        }
