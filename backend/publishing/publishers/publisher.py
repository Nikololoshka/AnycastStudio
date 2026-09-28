from types import ModuleType

from platforms.core.capabilities import Capabilities, Validator
from platforms.core.publishing import Publisher


class AppPublisher(Publisher, Validator):
    platform: ModuleType

    @property
    def label(self) -> str:
        return self.platform.LABEL

    def capabilities(self) -> Capabilities:
        return self.platform.capabilities()
