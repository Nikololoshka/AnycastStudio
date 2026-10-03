from typing import override

from platforms2.core import PlatformCapabilities, PlatformValidator, PublishDraft, PublishMedia, ValidationResult


class XValidator(PlatformValidator):
    MAX_TEXT_LENGTH = 280
    MIN_DURATION_SECONDS = 0.5
    MAX_DURATION_SECONDS = 140

    def __init__(self, capabilities: PlatformCapabilities):
        self._capabilities = capabilities

    @override
    def validate(self, draft: PublishDraft, media: PublishMedia) -> ValidationResult:
        errors: list[str] = []

        if self._utf16_length(draft.caption()) > self.MAX_TEXT_LENGTH:
            errors.append("captionTooLong")

        if not self._capabilities.fits(media.size_bytes):
            errors.append("fileTooLarge")

        if not self._capabilities.supports(media.mime_type):
            errors.append("unsupportedType")

        if media.duration_seconds and media.duration_seconds < self.MIN_DURATION_SECONDS:
            errors.append("videoTooShort")

        if media.duration_seconds and media.duration_seconds > self.MAX_DURATION_SECONDS:
            errors.append("videoTooLong")

        return ValidationResult(tuple(errors))

    @staticmethod
    def _utf16_length(text: str) -> int:
        return len(text.encode("utf-16-le")) // 2
