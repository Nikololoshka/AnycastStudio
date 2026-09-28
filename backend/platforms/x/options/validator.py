from ...core.capabilities import ValidationResult, Validator
from ...core.publishing import PublicationDraft
from .capabilities import MAX_FILE_BYTES, SUPPORTED_MIME_TYPES

MAX_TEXT_LENGTH = 280
MIN_DURATION_SECONDS = 0.5
MAX_DURATION_SECONDS = 140


class XValidator(Validator):
    def validate(self, draft: PublicationDraft) -> ValidationResult:
        media = draft.media
        errors: list[str] = []

        if self.utf16_length(draft.caption()) > MAX_TEXT_LENGTH:
            errors.append("captionTooLong")

        if media.size_bytes > MAX_FILE_BYTES:
            errors.append("fileTooLarge")

        if media.mime_type and media.mime_type not in SUPPORTED_MIME_TYPES:
            errors.append("unsupportedType")

        if media.duration_seconds and media.duration_seconds < MIN_DURATION_SECONDS:
            errors.append("videoTooShort")

        if media.duration_seconds and media.duration_seconds > MAX_DURATION_SECONDS:
            errors.append("videoTooLong")

        return ValidationResult(valid=not errors, errors=errors)

    @staticmethod
    def utf16_length(text: str) -> int:
        return len(text.encode("utf-16-le")) // 2
