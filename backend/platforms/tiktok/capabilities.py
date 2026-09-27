from ..capabilities import Capabilities, Scheduling, ValidationResult
from .video_options import MAX_CAPTION_LENGTH, PRIVATE, VideoOptions, utf16_length

LABEL = "TikTok"

MAX_FILE_BYTES = 4 * 1024**3

SUPPORTED_MIME_TYPES = ("video/mp4", "video/quicktime", "video/webm")


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


def validate(*, caption: str, options: VideoOptions, size_bytes: int, mime_type: str) -> ValidationResult:
    errors: list[str] = []

    if utf16_length(caption) > MAX_CAPTION_LENGTH:
        errors.append("captionTooLong")

    if options.privacy_level is None:
        errors.append("privacyRequired")

    if options.disclose_content and not (options.brand_organic or options.brand_content):
        errors.append("commercialContentUnspecified")

    if options.brand_content_toggle and options.privacy_level == PRIVATE:
        errors.append("brandedContentCannotBePrivate")

    if size_bytes > MAX_FILE_BYTES:
        errors.append("fileTooLarge")

    if mime_type and mime_type not in SUPPORTED_MIME_TYPES:
        errors.append("unsupportedType")

    return ValidationResult(valid=not errors, errors=errors)
