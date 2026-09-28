from abc import ABC, abstractmethod

from .job import PublishJob
from .outcome import Confirmation, Published


class Publisher(ABC):
    label: str

    @abstractmethod
    def upload(self, job: PublishJob, access_token: str, on_progress, should_cancel) -> str: ...

    def publish(self, job: PublishJob, media_id: str, access_token: str) -> Published:
        return Published.awaiting_confirmation()

    def confirm(self, job: PublishJob, access_token: str) -> Confirmation:
        raise NotImplementedError(f"{self.label} publishes without waiting for confirmation")

    def commit(self, job: PublishJob, access_token: str) -> Published:
        raise NotImplementedError(f"{self.label} has no step to commit")

    def resolve_uncertain(self, job: PublishJob, access_token: str) -> Published | None:
        return None
