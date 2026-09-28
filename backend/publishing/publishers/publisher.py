from abc import ABC, abstractmethod
from pathlib import Path
from types import ModuleType

from media import storage
from platforms.core.capabilities import Capabilities, ValidationResult

from ..models import PublicationTarget
from .outcome import Published, awaiting_confirmation


class Publisher(ABC):
    platform: ModuleType

    def capabilities(self) -> Capabilities:
        return self.platform.capabilities()

    def caption(self, target: PublicationTarget) -> str:
        publication = target.publication
        return self.platform.caption_of(publication.title, publication.description, list(publication.hashtags))

    def file_of(self, target: PublicationTarget) -> Path:
        return storage.absolute(target.publication.asset.storage_path)

    @abstractmethod
    def validate(self, target: PublicationTarget) -> ValidationResult: ...

    @abstractmethod
    def upload(
        self, target: PublicationTarget, access_token: str, resume: dict | None, on_progress, should_cancel
    ) -> str: ...

    def publish(self, target: PublicationTarget, media_id: str, access_token: str) -> Published:
        return awaiting_confirmation()

    def confirm(self, target: PublicationTarget, access_token: str) -> Published | None:
        raise NotImplementedError(f"{self.platform.LABEL} publishes without waiting for confirmation")
