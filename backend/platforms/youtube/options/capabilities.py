from ...core.capabilities import Capabilities, Scheduling
from ..client import LABEL

MAX_FILE_BYTES = 128 * 1024**3

SUPPORTED_MIME_TYPES = (
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-ms-wmv",
    "video/x-flv",
    "video/3gpp",
    "video/webm",
    "video/mpeg",
)

CAPABILITIES = Capabilities(
    label=LABEL,
    scheduling=Scheduling.NATIVE,
    title=True,
    description=True,
    hashtags=True,
    drafts=True,
    max_file_size=MAX_FILE_BYTES,
    supported_mime_types=SUPPORTED_MIME_TYPES,
)
