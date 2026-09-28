from ...core.capabilities import Capabilities, Scheduling
from ..client import LABEL

MAX_FILE_BYTES = 300 * 1000**2

SUPPORTED_MIME_TYPES = ("video/mp4", "video/quicktime")

CAPABILITIES = Capabilities(
    label=LABEL,
    scheduling=Scheduling.DEFERRED_UPLOAD,
    title=True,
    description=True,
    hashtags=True,
    drafts=False,
    max_file_size=MAX_FILE_BYTES,
    supported_mime_types=SUPPORTED_MIME_TYPES,
)
