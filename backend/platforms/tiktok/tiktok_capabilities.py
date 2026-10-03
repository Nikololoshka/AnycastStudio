from dataclasses import dataclass

from platforms.core import PlatformCapabilities, Scheduling


@dataclass(frozen=True)
class TikTokCapabilities(PlatformCapabilities):
    label: str = "TikTok"
    scheduling: Scheduling = Scheduling.DEFERRED_UPLOAD
    title: bool = True
    description: bool = True
    hashtags: bool = True
    drafts: bool = False
    max_file_size: int | None = 4 * 1024**3
    supported_mime_types: tuple[str, ...] = ("video/mp4", "video/quicktime", "video/webm")
