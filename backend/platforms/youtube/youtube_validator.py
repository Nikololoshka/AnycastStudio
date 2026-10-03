from typing import override

from platforms.core import PlatformCapabilities, PlatformValidator, PublishDraft, PublishMedia, ValidationResult


class YouTubeValidator(PlatformValidator):
    MAX_TITLE_LENGTH = 100
    MAX_DESCRIPTION_LENGTH = 5000

    def __init__(self, capabilities: PlatformCapabilities):
        self._capabilities = capabilities

    @override
    def validate(self, draft: PublishDraft, media: PublishMedia) -> ValidationResult:
        errors: list[str] = []

        if not draft.title.strip():
            errors.append("titleRequired")
        elif len(draft.title) > self.MAX_TITLE_LENGTH:
            errors.append("titleTooLong")

        if len(draft.description) > self.MAX_DESCRIPTION_LENGTH:
            errors.append("descriptionTooLong")

        if not self._capabilities.fits(media.size_bytes):
            errors.append("fileTooLarge")

        if not self._capabilities.supports(media.mime_type):
            errors.append("unsupportedType")

        return ValidationResult(tuple(errors))
