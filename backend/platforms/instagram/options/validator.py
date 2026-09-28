import re

from ...core.capabilities import ValidationResult, Validator
from ...core.publishing import PublicationDraft
from .capabilities import MAX_FILE_BYTES, SUPPORTED_MIME_TYPES

MAX_CAPTION_LENGTH = 2200
MAX_HASHTAGS = 30
MIN_DURATION_SECONDS = 3
MAX_DURATION_SECONDS = 15 * 60

HASHTAG = re.compile(r"(?<![\w#])#\w+")


class InstagramValidator(Validator):
    def validate(self, draft: PublicationDraft) -> ValidationResult:
        caption = draft.caption()
        media = draft.media
        errors: list[str] = []

        if len(caption) > MAX_CAPTION_LENGTH:
            errors.append("captionTooLong")

        if len(HASHTAG.findall(caption)) > MAX_HASHTAGS:
            errors.append("tooManyHashtags")

        if media.size_bytes > MAX_FILE_BYTES:
            errors.append("fileTooLarge")

        if media.mime_type and media.mime_type not in SUPPORTED_MIME_TYPES:
            errors.append("unsupportedType")

        if media.duration_seconds and media.duration_seconds < MIN_DURATION_SECONDS:
            errors.append("videoTooShort")

        if media.duration_seconds and media.duration_seconds > MAX_DURATION_SECONDS:
            errors.append("videoTooLong")

        return ValidationResult(valid=not errors, errors=errors)
