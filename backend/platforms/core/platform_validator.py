from abc import ABC, abstractmethod

from .publish import PublishDraft, PublishMedia
from .validation_result import ValidationResult


class PlatformValidator(ABC):

    @abstractmethod
    def validate(self, draft: PublishDraft, media: PublishMedia) -> ValidationResult: ...
