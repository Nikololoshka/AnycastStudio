from ..capabilities import Capabilities, Scheduling, ValidationResult
from .client import LABEL
from .video_options import MAX_CAPTION_LENGTH, MAX_HASHTAGS, hashtag_count

MAX_FILE_BYTES = 300 * 1000**2
MIN_DURATION_SECONDS = 3
MAX_DURATION_SECONDS = 15 * 60

SUPPORTED_MIME_TYPES = ("video/mp4", "video/quicktime")


def capabilities() -> Capabilities:
    return Capabilities(
        label=LABEL,
        scheduling=Scheduling.DEFERRED_UPLOAD,
        title=True,
        description=True,
        hashtags=True,
        drafts=False,
        max_file_size=MAX_FILE_BYTES,
        supported_mime_types=SUPPORTED_MIME_TYPES,
    )


def validate(*, caption: str, size_bytes: int, mime_type: str, duration_seconds: float | None) -> ValidationResult:
    errors: list[str] = []

    if len(caption) > MAX_CAPTION_LENGTH:
        errors.append("captionTooLong")

    if hashtag_count(caption) > MAX_HASHTAGS:
        errors.append("tooManyHashtags")

    if size_bytes > MAX_FILE_BYTES:
        errors.append("fileTooLarge")

    if mime_type and mime_type not in SUPPORTED_MIME_TYPES:
        errors.append("unsupportedType")

    if duration_seconds and duration_seconds < MIN_DURATION_SECONDS:
        errors.append("videoTooShort")

    if duration_seconds and duration_seconds > MAX_DURATION_SECONDS:
        errors.append("videoTooLong")

    return ValidationResult(valid=not errors, errors=errors)
