from ...core.capabilities import ValidationResult, Validator
from ...core.publishing import PublicationDraft
from .capabilities import MAX_FILE_BYTES, SUPPORTED_MIME_TYPES
from .options import TikTokOptions

MAX_CAPTION_LENGTH = 2200


class TikTokValidator(Validator):
    def validate(self, draft: PublicationDraft) -> ValidationResult:
        options = TikTokOptions.of(draft.settings)
        errors: list[str] = []

        if self.utf16_length(draft.caption()) > MAX_CAPTION_LENGTH:
            errors.append("captionTooLong")

        if options.privacy_level is None:
            errors.append("privacyRequired")

        if options.disclose_content and not (options.brand_organic or options.brand_content):
            errors.append("commercialContentUnspecified")

        if options.brand_content_toggle and options.is_private:
            errors.append("brandedContentCannotBePrivate")

        if draft.media.size_bytes > MAX_FILE_BYTES:
            errors.append("fileTooLarge")

        mime_type = draft.media.mime_type
        if mime_type and mime_type not in SUPPORTED_MIME_TYPES:
            errors.append("unsupportedType")

        return ValidationResult(valid=not errors, errors=errors)

    @staticmethod
    def utf16_length(text: str) -> int:
        return len(text.encode("utf-16-le")) // 2
