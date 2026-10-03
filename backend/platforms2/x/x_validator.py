from typing import override

from platforms2.core import PlatformValidator, PublishDraft, PublishMedia, ValidationResult


class XValidator(PlatformValidator):
    MAX_TEXT_LENGTH = 280
    MIN_DURATION_SECONDS = 0.5
    MAX_DURATION_SECONDS = 140
    MAX_FILE_BYTES = 512 * 1024**2
    SUPPORTED_MIME_TYPES = ("video/mp4", "video/quicktime")

    @override
    def validate(self, draft: PublishDraft, media: PublishMedia) -> ValidationResult:
        errors: list[str] = []

        if self._utf16_length(draft.caption()) > self.MAX_TEXT_LENGTH:
            errors.append("captionTooLong")

        if media.size_bytes > self.MAX_FILE_BYTES:
            errors.append("fileTooLarge")

        if media.mime_type and media.mime_type not in self.SUPPORTED_MIME_TYPES:
            errors.append("unsupportedType")

        if media.duration_seconds and media.duration_seconds < self.MIN_DURATION_SECONDS:
            errors.append("videoTooShort")

        if media.duration_seconds and media.duration_seconds > self.MAX_DURATION_SECONDS:
            errors.append("videoTooLong")

        return ValidationResult(tuple(errors))

    @staticmethod
    def _utf16_length(text: str) -> int:
        return len(text.encode("utf-16-le")) // 2
