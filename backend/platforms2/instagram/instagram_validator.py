import re
from typing import override

from platforms2.core import PlatformValidator, PublishDraft, PublishMedia, ValidationResult


class InstagramValidator(PlatformValidator):
    MAX_CAPTION_LENGTH = 2200
    MAX_HASHTAGS = 30
    MIN_DURATION_SECONDS = 3
    MAX_DURATION_SECONDS = 15 * 60
    MAX_FILE_BYTES = 300 * 1000**2
    SUPPORTED_MIME_TYPES = ("video/mp4", "video/quicktime")
    HASHTAG = re.compile(r"(?<![\w#])#\w+")

    @override
    def validate(self, draft: PublishDraft, media: PublishMedia) -> ValidationResult:
        caption = draft.caption()
        errors: list[str] = []

        if len(caption) > self.MAX_CAPTION_LENGTH:
            errors.append("captionTooLong")

        if len(self.HASHTAG.findall(caption)) > self.MAX_HASHTAGS:
            errors.append("tooManyHashtags")

        if media.size_bytes > self.MAX_FILE_BYTES:
            errors.append("fileTooLarge")

        if media.mime_type and media.mime_type not in self.SUPPORTED_MIME_TYPES:
            errors.append("unsupportedType")

        if media.duration_seconds and media.duration_seconds < self.MIN_DURATION_SECONDS:
            errors.append("videoTooShort")

        if media.duration_seconds and media.duration_seconds > self.MAX_DURATION_SECONDS:
            errors.append("videoTooLong")

        return ValidationResult(tuple(errors))
