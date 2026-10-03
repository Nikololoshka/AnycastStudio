from typing import override

from platforms2.core import PlatformValidator, PublishDraft, PublishMedia, ValidationResult


class YouTubeValidator(PlatformValidator):
    MAX_TITLE_LENGTH = 100
    MAX_DESCRIPTION_LENGTH = 5000
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

    @override
    def validate(self, draft: PublishDraft, media: PublishMedia) -> ValidationResult:
        errors: list[str] = []

        if not draft.title.strip():
            errors.append("titleRequired")
        elif len(draft.title) > self.MAX_TITLE_LENGTH:
            errors.append("titleTooLong")

        if len(draft.description) > self.MAX_DESCRIPTION_LENGTH:
            errors.append("descriptionTooLong")

        if media.size_bytes > self.MAX_FILE_BYTES:
            errors.append("fileTooLarge")

        if media.mime_type and media.mime_type not in self.SUPPORTED_MIME_TYPES:
            errors.append("unsupportedType")

        return ValidationResult(tuple(errors))
