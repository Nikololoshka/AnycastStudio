from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from .confirmation import Confirmation
from .publish_job import PublishJob
from .publish_outcome import PublishOutcome
from .published import Published
from .upload_progress import UploadProgress


class PublishInteractor(ABC):

    @abstractmethod
    def upload(self, job: PublishJob, access_token: str) -> AsyncGenerator[UploadProgress]: ...

    @abstractmethod
    async def publish(self, job: PublishJob, access_token: str) -> PublishOutcome: ...

    async def confirm(self, job: PublishJob, access_token: str) -> Confirmation:
        raise NotImplementedError(f"{type(self).__name__} publishes without waiting for confirmation")

    async def commit(self, job: PublishJob, access_token: str) -> Published:
        raise NotImplementedError(f"{type(self).__name__} has no step to commit")

    async def resolve_uncertain(self, job: PublishJob, access_token: str) -> Published | None:
        return None
