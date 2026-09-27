from ..capabilities import Capabilities, Scheduling, ValidationResult
from .video_options import MAX_DESCRIPTION_LENGTH, MAX_TITLE_LENGTH

LABEL = "YouTube"

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


def capabilities() -> Capabilities:
    return Capabilities(
        label=LABEL,
        scheduling=Scheduling.NATIVE,
        title=True,
        description=True,
        hashtags=True,
        drafts=True,
        max_file_size=MAX_FILE_BYTES,
        supported_mime_types=SUPPORTED_MIME_TYPES,
    )


def validate(*, title: str, description: str, size_bytes: int, mime_type: str) -> ValidationResult:
    errors: list[str] = []

    if not title.strip():
        errors.append("titleRequired")
    elif len(title) > MAX_TITLE_LENGTH:
        errors.append("titleTooLong")

    if len(description) > MAX_DESCRIPTION_LENGTH:
        errors.append("descriptionTooLong")

    if size_bytes > MAX_FILE_BYTES:
        errors.append("fileTooLarge")

    if mime_type and mime_type not in SUPPORTED_MIME_TYPES:
        errors.append("unsupportedType")

    return ValidationResult(valid=not errors, errors=errors)
