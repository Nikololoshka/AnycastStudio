from dataclasses import dataclass
from typing import Self

from ...core.publishing import PublishJob
from ..options import YouTubeOptions


@dataclass(frozen=True)
class VideoMetadata:
    title: str
    description: str
    tags: tuple[str, ...]
    privacy_status: str
    category_id: str
    license: str
    embeddable: bool
    public_stats_viewable: bool
    made_for_kids: bool
    contains_synthetic_media: bool
    notify_subscribers: bool

    @classmethod
    def of(cls, job: PublishJob, options: YouTubeOptions) -> Self:
        draft = job.draft
        return cls(
            title=draft.title,
            description=options.description_with(draft.description, draft.hashtags),
            tags=draft.hashtags,
            privacy_status="private" if job.publish_at else options.privacy_status,
            category_id=options.category_id,
            license=options.license,
            embeddable=options.embeddable,
            public_stats_viewable=options.public_stats_viewable,
            made_for_kids=options.made_for_kids,
            contains_synthetic_media=options.contains_synthetic_media,
            notify_subscribers=options.notify_subscribers,
        )

    def as_body(self) -> dict:
        return {
            "snippet": {
                "title": self.title,
                "description": self.description,
                "tags": list(self.tags),
                "categoryId": self.category_id,
            },
            "status": {
                "privacyStatus": self.privacy_status,
                "license": self.license,
                "embeddable": self.embeddable,
                "publicStatsViewable": self.public_stats_viewable,
                "selfDeclaredMadeForKids": self.made_for_kids,
                "containsSyntheticMedia": self.contains_synthetic_media,
            },
        }
