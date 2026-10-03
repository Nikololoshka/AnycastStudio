from typing import override

from platforms2.core import PlatformValidator, PublishDraft, PublishMedia, ValidationResult

from .publish.tiktok_options import TikTokOptions


class TikTokValidator(PlatformValidator):
    MAX_CAPTION_LENGTH = 2200
    MAX_FILE_BYTES = 4 * 1024**3
    SUPPORTED_MIME_TYPES = ("video/mp4", "video/quicktime", "video/webm")

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

        if media.size_bytes > self.MAX_FILE_BYTES:
            errors.append("fileTooLarge")

        if media.mime_type and media.mime_type not in self.SUPPORTED_MIME_TYPES:
            errors.append("unsupportedType")

        return ValidationResult(tuple(errors))

    @staticmethod
    def _utf16_length(text: str) -> int:
        return len(text.encode("utf-16-le")) // 2
