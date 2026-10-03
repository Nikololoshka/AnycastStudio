import re
from typing import override

from platforms2.core import PlatformCapabilities, PlatformValidator, PublishDraft, PublishMedia, ValidationResult


class InstagramValidator(PlatformValidator):
    MAX_CAPTION_LENGTH = 2200
    MAX_HASHTAGS = 30
    MIN_DURATION_SECONDS = 3
    MAX_DURATION_SECONDS = 15 * 60
    HASHTAG = re.compile(r"(?<![\w#])#\w+")

    def __init__(self, capabilities: PlatformCapabilities):
        self._capabilities = capabilities

    @override
    def validate(self, draft: PublishDraft, media: PublishMedia) -> ValidationResult:
        caption = draft.caption()
        errors: list[str] = []

        if len(caption) > self.MAX_CAPTION_LENGTH:
            errors.append("captionTooLong")

        if len(self.HASHTAG.findall(caption)) > self.MAX_HASHTAGS:
            errors.append("tooManyHashtags")

        if not self._capabilities.fits(media.size_bytes):
            errors.append("fileTooLarge")

        if not self._capabilities.supports(media.mime_type):
            errors.append("unsupportedType")

        if media.duration_seconds and media.duration_seconds < self.MIN_DURATION_SECONDS:
            errors.append("videoTooShort")

        if media.duration_seconds and media.duration_seconds > self.MAX_DURATION_SECONDS:
            errors.append("videoTooLong")

        return ValidationResult(tuple(errors))
