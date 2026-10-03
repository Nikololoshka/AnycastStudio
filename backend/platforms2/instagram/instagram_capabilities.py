from dataclasses import dataclass

from platforms2.core import PlatformCapabilities, Scheduling


@dataclass(frozen=True)
class InstagramCapabilities(PlatformCapabilities):
    label: str = "Instagram"
    scheduling: Scheduling = Scheduling.DEFERRED_UPLOAD
    title: bool = True
    description: bool = True
    hashtags: bool = True
    drafts: bool = False
    max_file_size: int | None = 300 * 1000**2
    supported_mime_types: tuple[str, ...] = ("video/mp4", "video/quicktime")
