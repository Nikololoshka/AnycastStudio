from dataclasses import asdict, dataclass

PRIVACY_VALUES = ("private", "unlisted", "public")
LICENSE_VALUES = ("youtube", "creativeCommon")
CATEGORY_IDS = (
    "1", "2", "10", "15", "17", "19", "20", "22", "23", "24", "25", "26", "27", "28",
)

MAX_TITLE_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 5000
MAX_DESCRIPTION_HASHTAGS = 15

JSON_KEYS = {
    "privacy_status": "privacyStatus",
    "category_id": "categoryId",
    "made_for_kids": "madeForKids",
    "notify_subscribers": "notifySubscribers",
    "contains_synthetic_media": "containsSyntheticMedia",
    "public_stats_viewable": "publicStatsViewable",
    "hashtags_in_description": "hashtagsInDescription",
}


@dataclass(frozen=True)
class VideoOptions:
    privacy_status: str = "private"
    category_id: str = "22"
    license: str = "youtube"
    made_for_kids: bool = False
    notify_subscribers: bool = True
    contains_synthetic_media: bool = False
    embeddable: bool = True
    public_stats_viewable: bool = True
    hashtags_in_description: bool = True

    def as_json(self) -> dict:
        return {JSON_KEYS.get(key, key): value for key, value in asdict(self).items()}


def _one_of(value, allowed, fallback):
    return value if value in allowed else fallback


def _flag(raw: dict, key: str, fallback: bool) -> bool:
    value = raw.get(key)
    return fallback if value is None else bool(value)


def video_options_of(raw) -> VideoOptions:
    raw = raw if isinstance(raw, dict) else {}
    default = VideoOptions()

    return VideoOptions(
        privacy_status=_one_of(raw.get("privacyStatus"), PRIVACY_VALUES, default.privacy_status),
        category_id=_one_of(raw.get("categoryId"), CATEGORY_IDS, default.category_id),
        license=_one_of(raw.get("license"), LICENSE_VALUES, default.license),
        made_for_kids=_flag(raw, "madeForKids", default.made_for_kids),
        notify_subscribers=_flag(raw, "notifySubscribers", default.notify_subscribers),
        contains_synthetic_media=_flag(raw, "containsSyntheticMedia", default.contains_synthetic_media),
        embeddable=_flag(raw, "embeddable", default.embeddable),
        public_stats_viewable=_flag(raw, "publicStatsViewable", default.public_stats_viewable),
        hashtags_in_description=_flag(raw, "hashtagsInDescription", default.hashtags_in_description),
    )


def description_with_hashtags(description: str, hashtags: list[str], options: VideoOptions) -> str:
    if not options.hashtags_in_description or not hashtags:
        return description

    tags = " ".join(f"#{tag}" for tag in hashtags[:MAX_DESCRIPTION_HASHTAGS])
    return "\n\n".join(part for part in (description, tags) if part)
