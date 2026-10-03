from dataclasses import dataclass

from platforms2.core import PlatformCapabilities, Scheduling


@dataclass(frozen=True)
class XCapabilities(PlatformCapabilities):
    label: str = "X"
    scheduling: Scheduling = Scheduling.DEFERRED_UPLOAD
    title: bool = True
    description: bool = True
    hashtags: bool = True
    drafts: bool = False
    max_file_size: int | None = 512 * 1024**2
    supported_mime_types: tuple[str, ...] = ("video/mp4", "video/quicktime")
