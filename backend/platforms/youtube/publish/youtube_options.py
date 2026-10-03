from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, Self


@dataclass(frozen=True)
class YouTubeOptions:
    PRIVACY_VALUES: ClassVar = ("private", "unlisted", "public")
    LICENSE_VALUES: ClassVar = ("youtube", "creativeCommon")
    CATEGORY_IDS: ClassVar = ("1", "2", "10", "15", "17", "19", "20", "22", "23", "24", "25", "26", "27", "28")
    MAX_DESCRIPTION_HASHTAGS: ClassVar = 15

    privacy_status: str = "private"
    category_id: str = "22"
    license: str = "youtube"
    made_for_kids: bool = False
    notify_subscribers: bool = True
    contains_synthetic_media: bool = False
    embeddable: bool = True
    public_stats_viewable: bool = True
    hashtags_in_description: bool = True

    @classmethod
    def of(cls, raw: Mapping) -> Self:
        default = cls()
        return cls(
            privacy_status=cls._one_of(raw.get("privacyStatus"), cls.PRIVACY_VALUES, default.privacy_status),
            category_id=cls._one_of(raw.get("categoryId"), cls.CATEGORY_IDS, default.category_id),
            license=cls._one_of(raw.get("license"), cls.LICENSE_VALUES, default.license),
            made_for_kids=cls._flag(raw, "madeForKids", default.made_for_kids),
            notify_subscribers=cls._flag(raw, "notifySubscribers", default.notify_subscribers),
            contains_synthetic_media=cls._flag(raw, "containsSyntheticMedia", default.contains_synthetic_media),
            embeddable=cls._flag(raw, "embeddable", default.embeddable),
            public_stats_viewable=cls._flag(raw, "publicStatsViewable", default.public_stats_viewable),
            hashtags_in_description=cls._flag(raw, "hashtagsInDescription", default.hashtags_in_description),
        )

    def as_json(self) -> dict:
        return {
            "privacyStatus": self.privacy_status,
            "categoryId": self.category_id,
            "license": self.license,
            "madeForKids": self.made_for_kids,
            "notifySubscribers": self.notify_subscribers,
            "containsSyntheticMedia": self.contains_synthetic_media,
            "embeddable": self.embeddable,
            "publicStatsViewable": self.public_stats_viewable,
            "hashtagsInDescription": self.hashtags_in_description,
        }

    def description_with(self, description: str, hashtags: tuple[str, ...]) -> str:
        if not self.hashtags_in_description or not hashtags:
            return description
        tags = " ".join(f"#{tag}" for tag in hashtags[: self.MAX_DESCRIPTION_HASHTAGS])
        return "\n\n".join(part for part in (description, tags) if part)

    def status_fields(self) -> dict:
        return {
            "license": self.license,
            "embeddable": self.embeddable,
            "publicStatsViewable": self.public_stats_viewable,
            "selfDeclaredMadeForKids": self.made_for_kids,
            "containsSyntheticMedia": self.contains_synthetic_media,
        }

    @staticmethod
    def _one_of(value, allowed: tuple[str, ...], fallback: str) -> str:
        return value if value in allowed else fallback

    @staticmethod
    def _flag(raw: Mapping, key: str, fallback: bool) -> bool:
        value = raw.get(key)
        return fallback if value is None else bool(value)
