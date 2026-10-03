from typing import override

from platforms2.core import PlatformCapabilities, PlatformValidator, PublishDraft, PublishMedia, ValidationResult

from .publish.tiktok_options import TikTokOptions


class TikTokValidator(PlatformValidator):
    MAX_CAPTION_LENGTH = 2200

    def __init__(self, capabilities: PlatformCapabilities):
        self._capabilities = capabilities

    @override
    def validate(self, draft: PublishDraft, media: PublishMedia) -> ValidationResult:
        options = TikTokOptions.of(draft.settings)
        errors: list[str] = []

        if self._utf16_length(draft.caption()) > self.MAX_CAPTION_LENGTH:
            errors.append("captionTooLong")

        if options.privacy_level is None:
            errors.append("privacyRequired")

        if options.disclose_content and not (options.brand_organic or options.brand_content):
            errors.append("commercialContentUnspecified")

        if options.brand_content_toggle and options.is_private:
            errors.append("brandedContentCannotBePrivate")

        if not self._capabilities.fits(media.size_bytes):
            errors.append("fileTooLarge")

        if not self._capabilities.supports(media.mime_type):
            errors.append("unsupportedType")

        return ValidationResult(tuple(errors))

    @staticmethod
    def _utf16_length(text: str) -> int:
        return len(text.encode("utf-16-le")) // 2
