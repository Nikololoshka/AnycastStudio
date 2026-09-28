from abc import ABC, abstractmethod

from ..publishing.job import PublicationDraft
from .validation import ValidationResult


class Validator(ABC):
    @abstractmethod
    def validate(self, draft: PublicationDraft) -> ValidationResult: ...
