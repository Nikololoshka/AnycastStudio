from types import ModuleType

from platforms.core.capabilities import Capabilities, ValidationResult
from platforms.core.publishing import Publisher, PublishJob


class AppPublisher(Publisher):
    platform: ModuleType

    @property
    def label(self) -> str:
        return self.platform.LABEL

    def capabilities(self) -> Capabilities:
        return self.platform.capabilities()

    def validate(self, job: PublishJob) -> ValidationResult:
        raise NotImplementedError
