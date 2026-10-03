from dataclasses import dataclass

from platforms2.core import PlatformCapabilities, Scheduling


@dataclass(frozen=True)
class YouTubeCapabilities(PlatformCapabilities):
    label: str = "YouTube"
    scheduling: Scheduling = Scheduling.NATIVE
    title: bool = True
    description: bool = True
    hashtags: bool = True
    drafts: bool = True
    max_file_size: int | None = 128 * 1024**3
    supported_mime_types: tuple[str, ...] = (
        "video/mp4",
        "video/quicktime",
        "video/x-msvideo",
        "video/x-ms-wmv",
        "video/x-flv",
        "video/3gpp",
        "video/webm",
        "video/mpeg",
    )
