from ...core.capabilities import ValidationResult, Validator
from ...core.publishing import PublicationDraft
from .capabilities import MAX_FILE_BYTES, SUPPORTED_MIME_TYPES

MAX_TITLE_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 5000


class YouTubeValidator(Validator):
    def validate(self, draft: PublicationDraft) -> ValidationResult:
        errors: list[str] = []

        if not draft.title.strip():
            errors.append("titleRequired")
        elif len(draft.title) > MAX_TITLE_LENGTH:
            errors.append("titleTooLong")

        if len(draft.description) > MAX_DESCRIPTION_LENGTH:
            errors.append("descriptionTooLong")

        if draft.media.size_bytes > MAX_FILE_BYTES:
            errors.append("fileTooLarge")

        mime_type = draft.media.mime_type
        if mime_type and mime_type not in SUPPORTED_MIME_TYPES:
            errors.append("unsupportedType")

        return ValidationResult(valid=not errors, errors=errors)
